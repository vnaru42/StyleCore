"""Print-only map theme support for StyleCore.

This module intentionally does not participate in automatic styling, template
synchronisation or print-layout discovery.  It only maintains a project map
 theme named ``PRINT`` whose layer styles are copies of the current styles with
marker symbols scaled by a user-selected percentage.
"""

from qgis.core import (
    QgsMapThemeCollection,
    QgsMarkerSymbol,
    QgsLayoutItemMap,
    QgsMessageLog,
    QgsProject,
    QgsRenderContext,
    Qgis,
)
from qgis.PyQt.QtCore import QSettings, QTimer

from .config import PRINT_SCALE_KEY

PRINT_THEME_NAME = "PRINT"
PRINT_STYLE_NAME = "__STYLECORE_PRINT__"
DEFAULT_PRINT_SCALE = 80


class StyleCorePrintTheme:
    """Create/update the PRINT theme without changing the normal layer styles."""

    def __init__(self, iface):
        self.iface = iface
        self._refreshing = False

        # Coalesce automatic refresh requests. During project/template loading
        # QGIS can add many layers in quick succession; rebuilding PRINT for
        # every signal is unnecessary and can destabilise project loading.
        self._refresh_timer = QTimer()
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(1500)
        self._refresh_timer.timeout.connect(self.refresh_theme)

    def scale_percent(self):
        return QSettings().value(
            PRINT_SCALE_KEY,
            DEFAULT_PRINT_SCALE,
            type=int,
        )

    def set_scale_percent(self, value):
        value = max(25, min(100, int(value)))
        QSettings().setValue(PRINT_SCALE_KEY, value)
        # User explicitly pressed Apply in the options page.
        self._refresh_timer.stop()
        self.refresh_theme()

    def schedule_refresh(self, *args):
        # Restarting the timer makes this a debounce: PRINT is rebuilt once,
        # after QGIS has been idle long enough for layer/project loading to finish.
        if self._refreshing:
            return
        self._refresh_timer.start()

    def refresh_theme(self):
        """Rebuild PRINT styles and the PRINT map theme from current project state."""
        if self._refreshing:
            return

        project = QgsProject.instance()
        if not project.mapLayers():
            return

        try:
            self._refreshing = True
            factor = self.scale_percent() / 100.0

            for node in project.layerTreeRoot().findLayers():
                layer = node.layer()
                if layer is None or not layer.isValid():
                    continue
                self._refresh_layer_print_style(layer, factor)

            # Build the actual QGIS map theme from a real project state.
            # QGIS records the active named style for each visible layer when
            # createThemeFromCurrentState() is called.  We therefore switch
            # only the layers which have a private PRINT style, capture the
            # theme, and immediately restore every layer to its previous style.
            #
            # This is deliberately NOT connected to visibility-change signals;
            # it only runs after project/layer loading or when the user presses
            # Apply in StyleCore settings.  That keeps project opening stable.
            original_styles = self._activate_print_styles()
            try:
                collection = project.mapThemeCollection()
                record = QgsMapThemeCollection.createThemeFromCurrentState(
                    project.layerTreeRoot(),
                    self.iface.layerTreeView().model(),
                )

                if collection.hasMapTheme(PRINT_THEME_NAME):
                    collection.update(PRINT_THEME_NAME, record)
                else:
                    collection.insert(PRINT_THEME_NAME, record)
            finally:
                self._restore_styles(original_styles)

            if not project.mapThemeCollection().hasMapTheme(PRINT_THEME_NAME):
                raise RuntimeError("QGIS did not register the PRINT map theme")

            # Force the canvas and any layout map following PRINT to discard an
            # old cached render after the theme has been rebuilt.
            try:
                self.iface.mapCanvas().refresh()
            except Exception:
                pass
            self._refresh_print_layouts(project)
            project.setDirty(True)

        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Could not update PRINT theme: {exc}",
                "StyleCore",
                level=Qgis.Warning,
            )
        finally:
            self._refreshing = False


    def _refresh_print_layouts(self, project):
        """Refresh layout map items which explicitly follow the PRINT theme."""
        try:
            layouts = project.layoutManager().layouts()
        except Exception:
            return

        for layout in layouts:
            refresh_layout = False
            try:
                items = layout.items()
            except Exception:
                items = []

            for item in items:
                if not isinstance(item, QgsLayoutItemMap):
                    continue
                try:
                    if (
                        item.followVisibilityPreset()
                        and item.followVisibilityPresetName() == PRINT_THEME_NAME
                    ):
                        item.invalidateCache()
                        item.update()
                        refresh_layout = True
                except Exception:
                    continue

            if refresh_layout:
                try:
                    layout.refresh()
                except Exception:
                    pass

    def _refresh_layer_print_style(self, layer, factor):
        """Replace one layer's private PRINT style with a scaled copy."""
        if not hasattr(layer, "styleManager") or not hasattr(layer, "renderer"):
            return

        renderer = layer.renderer()
        if renderer is None or not self._renderer_has_markers(renderer):
            return

        manager = layer.styleManager()
        if manager is None:
            return

        original_style = manager.currentStyle()

        # Never use a stale PRINT style as the source for another scaling pass.
        if original_style == PRINT_STYLE_NAME:
            alternatives = [name for name in manager.styles() if name != PRINT_STYLE_NAME]
            if alternatives:
                manager.setCurrentStyle(alternatives[0])
                original_style = manager.currentStyle()

        if PRINT_STYLE_NAME in manager.styles():
            manager.removeStyle(PRINT_STYLE_NAME)

        if not manager.addStyleFromLayer(PRINT_STYLE_NAME):
            return

        manager.setCurrentStyle(PRINT_STYLE_NAME)
        try:
            print_renderer = layer.renderer()
            if print_renderer is not None:
                self._scale_renderer_markers(print_renderer, factor)
        finally:
            if original_style in manager.styles():
                manager.setCurrentStyle(original_style)

    def _renderer_has_markers(self, renderer):
        try:
            symbols = renderer.symbols(QgsRenderContext())
        except Exception:
            return False

        seen = set()
        return any(self._symbol_has_marker(symbol, seen) for symbol in symbols)

    def _symbol_has_marker(self, symbol, seen):
        if symbol is None:
            return False

        symbol_id = id(symbol)
        if symbol_id in seen:
            return False
        seen.add(symbol_id)

        if isinstance(symbol, QgsMarkerSymbol):
            return True

        try:
            count = symbol.symbolLayerCount()
        except Exception:
            count = 0

        for index in range(count):
            try:
                symbol_layer = symbol.symbolLayer(index)
                sub_symbol = symbol_layer.subSymbol()
            except Exception:
                sub_symbol = None
            if sub_symbol is not None and self._symbol_has_marker(sub_symbol, seen):
                return True

        return False

    def _scale_renderer_markers(self, renderer, factor):
        """Scale marker symbols, including nested marker sub-symbols."""
        try:
            symbols = renderer.symbols(QgsRenderContext())
        except Exception:
            symbols = []

        seen = set()
        for symbol in symbols:
            self._scale_symbol(symbol, factor, seen)

    def _scale_symbol(self, symbol, factor, seen):
        if symbol is None:
            return

        marker_id = id(symbol)
        if marker_id in seen:
            return
        seen.add(marker_id)

        if isinstance(symbol, QgsMarkerSymbol):
            symbol.setSize(symbol.size() * factor)
            return

        # Line/fill symbols can contain marker sub-symbols (marker lines,
        # geometry generators, etc.). Walk those without changing line widths.
        try:
            count = symbol.symbolLayerCount()
        except Exception:
            count = 0

        for index in range(count):
            try:
                symbol_layer = symbol.symbolLayer(index)
            except Exception:
                continue

            try:
                sub_symbol = symbol_layer.subSymbol()
            except Exception:
                sub_symbol = None

            if sub_symbol is not None:
                self._scale_symbol(sub_symbol, factor, seen)

    def _activate_print_styles(self):
        """Temporarily switch layers to PRINT style; return styles to restore."""
        original = {}
        project = QgsProject.instance()

        for node in project.layerTreeRoot().findLayers():
            layer = node.layer()
            if layer is None or not hasattr(layer, "styleManager"):
                continue

            manager = layer.styleManager()
            if manager is None or PRINT_STYLE_NAME not in manager.styles():
                continue

            original[layer.id()] = manager.currentStyle()
            manager.setCurrentStyle(PRINT_STYLE_NAME)

        return original

    def _restore_styles(self, original_styles):
        project = QgsProject.instance()
        for layer_id, style_name in original_styles.items():
            layer = project.mapLayer(layer_id)
            if layer is None or not hasattr(layer, "styleManager"):
                continue
            manager = layer.styleManager()
            if manager is not None and style_name in manager.styles():
                manager.setCurrentStyle(style_name)
