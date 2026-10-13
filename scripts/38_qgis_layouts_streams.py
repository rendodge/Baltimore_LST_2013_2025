"""QGIS print layouts (Letter portrait) for Report 1: stream corridors are cool because they are forested.

Run inside QGIS (Python console or MCP execute_code): exec(open(r"<repo>\\scripts\\38_qgis_layouts_streams.py").read())
Needs the project layers "B | Mean relative LST (°C vs city median)", "Tree canopy 2021/22 (%)",
"Canopy height 1 m (Meta, m)" and the group "Layout: stream corridors" (open channels, city boundary,
continuity points). Creates layout-only copies of the rasters, so existing layer styles are untouched.
Page 1: citywide LST + canopy, corridor-by-canopy chart (scripts/37). Page 2: Gwynns Falls zoom, four panels.
Exports PDF + 300 dpi PNG to figures/layouts/.
"""
import os

from qgis.core import (QgsColorRampLegendNode, QgsLegendRenderer, QgsMapLayerLegendUtils, QgsMapLayerType,
                       QgsMarkerSymbol, QgsPalLayerSettings, QgsPointXY, QgsTextBufferSettings,
                       QgsVectorLayerSimpleLabeling)
from qgis.core import (Qgis, QgsApplication, QgsColorRampLegendNodeSettings, QgsColorRampShader, QgsFeature,
                       QgsFillSymbol, QgsGeometry, QgsGradientColorRamp, QgsLayoutExporter, QgsLayoutItemLabel,
                       QgsLayoutItemLegend, QgsLayoutItemMap, QgsLayoutItemPage, QgsLayoutItemPicture,
                       QgsLayoutItemScaleBar, QgsLayoutMeasurement, QgsLayoutPoint, QgsLayoutSize, QgsLegendStyle,
                       QgsPrintLayout, QgsProject, QgsRasterLayer, QgsRasterShader, QgsRectangle,
                       QgsSingleBandPseudoColorRenderer, QgsSingleSymbolRenderer, QgsTextFormat, QgsUnitTypes,
                       QgsVectorLayer)
from qgis.PyQt.QtCore import QSize, Qt
from qgis.PyQt.QtGui import QColor, QFont

P = QgsProject.instance()
tree = P.layerTreeRoot()
MM = QgsUnitTypes.LayoutMillimeters
ROOTD = os.path.dirname(P.absolutePath()) if P.absolutePath() else r"C:\Users\rendo\Documents\QGIS_Baltimore_LST"
OUTD = os.path.join(ROOTD, "figures", "layouts")
ZOOM = QgsRectangle(353900, 4348200, 358700, 4353000)  # Gwynns Falls, Leakin Park downstream
ZOOM3 = QgsRectangle(356900, 4351000, 362100, 4356200)  # lower Jones Falls: Druid Hill Park to downtown
FS = 2.0  # font scale: all layout text at 2x the original spec
L = lambda n: P.mapLayersByName(n)[0]  # noqa: E731
grp = tree.findGroup("Layout: stream corridors") or tree.insertGroup(0, "Layout: stream corridors")


def setup_vectors():
    """Open channels, city outline and continuity points (written to GeoPackages so the project reloads cleanly)."""
    import processing
    import pandas as pd
    from qgis.core import (QgsField, QgsFields, QgsGraduatedSymbolRenderer, QgsLineSymbol, QgsMarkerSymbol,
                           QgsPointXY, QgsRendererRange, QgsVectorFileWriter, QgsWkbTypes, QgsCoordinateReferenceSystem)
    from qgis.PyQt.QtCore import QVariant
    for n in ("Open stream channels", "Stream, no visible channel", "City boundary", "Along-stream forest continuity (%)"):
        for lyr in P.mapLayersByName(n):
            P.removeMapLayer(lyr)
    hid = QgsVectorLayer(os.path.join(ROOTD, "data", "vector", "streams_cc_city.gpkg"), "Stream, no visible channel", "ogr")
    hid.setSubsetString('"cnctR" >= 0.5')
    hid.setRenderer(QgsSingleSymbolRenderer(QgsLineSymbol.createSimple({"color": "70,70,70", "width": "0.35", "line_style": "dash"})))
    op = QgsVectorLayer(os.path.join(ROOTD, "data", "vector", "streams_cc_city.gpkg"), "Open stream channels", "ogr")
    op.setSubsetString('"cnctR" < 0.5')
    op.setRenderer(QgsSingleSymbolRenderer(QgsLineSymbol.createSimple({"color": "30,30,30", "width": "0.3", "capstyle": "round"})))
    outline = os.path.join(ROOTD, "data", "vector", "city_outline_32618.gpkg")
    if not os.path.exists(outline):
        processing.run("native:dissolve", {"INPUT": os.path.join(ROOTD, "data", "vector", "nsa_boundaries_32618.gpkg"), "OUTPUT": outline})
    city = QgsVectorLayer(outline, "City boundary", "ogr")
    city.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple({"color": "0,0,0,0", "outline_color": "60,60,60", "outline_width": "0.35"})))
    cpath = os.path.join(ROOTD, "data", "processed", "streams", "continuity_points.gpkg")
    d = pd.read_csv(os.path.join(ROOTD, "data", "processed", "streams", "buffer_points_v2.csv"), usecols=["x", "y", "continuity_can"]).dropna()
    flds = QgsFields()
    flds.append(QgsField("cont", QVariant.Double))
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    w = QgsVectorFileWriter.create(cpath, flds, QgsWkbTypes.Point, QgsCoordinateReferenceSystem("EPSG:32618"), P.transformContext(), opts)
    for x, y, c in d.itertuples(index=False):
        f = QgsFeature(flds)
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
        f["cont"] = float(c) * 100
        w.addFeature(f)
    del w
    pts = QgsVectorLayer(cpath, "Along-stream forest continuity (%)", "ogr")
    ranges = []
    for (lo, hi), c in zip([(0, 20), (20, 40), (40, 60), (60, 80), (80, 100)],
                           ["#ffffcc", "#a1dab4", "#41b6c4", "#2c7fb8", "#253494"]):
        s = QgsMarkerSymbol.createSimple({"name": "circle", "size": "2.5", "color": c, "outline_color": "20,20,20", "outline_width": "0.25"})
        ranges.append(QgsRendererRange(lo, hi, s, f"{lo}–{hi}%"))
    pts.setRenderer(QgsGraduatedSymbolRenderer("cont", ranges))
    for lyr in (pts, op, hid, city):
        P.addMapLayer(lyr, False)
        grp.addLayer(lyr).setItemVisibilityChecked(False)


setup_vectors()


def raster_copy(src_name, new_name):
    for lyr in P.mapLayersByName(new_name):
        P.removeMapLayer(lyr)
    s = L(src_name)
    r = QgsRasterLayer(s.source(), new_name)
    r.setRenderer(s.renderer().clone())
    P.addMapLayer(r, False)
    grp.addLayer(r).setItemVisibilityChecked(False)
    return r


def ramp_legend(r, lo, hi):
    st = QgsColorRampLegendNodeSettings()
    st.setUseContinuousLegend(True)
    st.setOrientation(Qt.Horizontal)
    st.setMinimumLabel(lo)
    st.setMaximumLabel(hi)
    r.renderer().shader().rasterShaderFunction().setLegendSettings(QgsColorRampLegendNodeSettings(st))
    r.triggerRepaint()


def tfmt(size, bold=False, color="#222222"):
    t = QgsTextFormat()
    f = QFont("Arial")
    f.setBold(bold)
    t.setFont(f)
    t.setSize(size)
    t.setSizeUnit(QgsUnitTypes.RenderPoints)
    t.setColor(QColor(color))
    return t


def label(lay, text, x, y, w, h, size, bold=False, color="#222222", html=False):
    it = QgsLayoutItemLabel(lay)
    if html:
        it.setMode(QgsLayoutItemLabel.ModeHtml)
        text = f'<div style="font-family:Arial; font-size:{size}pt; color:{color}; line-height:1.15">{text}</div>'
    it.setText(text)
    it.setTextFormat(tfmt(size, bold, color))
    lay.addLayoutItem(it)
    it.attemptMove(QgsLayoutPoint(x, y, MM))
    it.attemptResize(QgsLayoutSize(w, h, MM))
    return it


def mapitem(lay, layers, ext, x, y, w, h):
    m = QgsLayoutItemMap(lay)
    lay.addLayoutItem(m)
    m.attemptMove(QgsLayoutPoint(x, y, MM))
    m.attemptResize(QgsLayoutSize(w, h, MM))
    m.setCrs(P.crs())
    m.setLayers(layers)
    m.setKeepLayerSet(True)
    m.zoomToExtent(ext)
    m.setFrameEnabled(True)
    m.setFrameStrokeWidth(QgsLayoutMeasurement(0.2, MM))
    m.setFrameStrokeColor(QColor("#555555"))
    m.setBackgroundColor(QColor("white"))
    return m


def legend(lay, m, entries, x, y, sym=(5.0, 3.0), cols=1, hide_titles=False):
    """entries: (layer, name). Rasters show only their colour ramp under the name; single-symbol vectors show
    the symbol with the name; graduated vectors show the name as a heading over their classes."""
    lg = QgsLayoutItemLegend(lay)
    lay.addLayoutItem(lg)
    lg.setLinkedMap(m)
    lg.setAutoUpdateModel(False)
    model = lg.model()
    rg = model.rootGroup()
    rg.removeAllChildren()
    for lyr, nm in entries:
        nd = rg.addLayer(lyr)
        nd.setUseLayerName(False)
        nd.setName(nm)
        nd.setCustomProperty("legend/title-label", nm)
        nodes = model.layerLegendNodes(nd)
        if lyr.type() == QgsMapLayerType.RasterLayer:  # drop the "Band 1 ..." row, keep the ramp
            keep = [i for i, n in enumerate(nodes) if isinstance(n, QgsColorRampLegendNode)]
            QgsMapLayerLegendUtils.setLegendNodeOrder(nd, keep)
        elif len(nodes) == 1:  # single symbol: label the symbol itself
            QgsMapLayerLegendUtils.setLegendNodeUserLabel(nd, 0, nm)
            QgsLegendRenderer.setNodeLegendStyle(nd, QgsLegendStyle.Hidden)
        elif hide_titles:  # classes only (title placed as a separate label)
            QgsLegendRenderer.setNodeLegendStyle(nd, QgsLegendStyle.Hidden)
        model.refreshLayerLegend(nd)
    lg.setTitle("")
    lg.setBoxSpace(0.5)
    lg.setSplitLayer(cols > 1)
    for st, sz, b in ((QgsLegendStyle.Title, 8, True), (QgsLegendStyle.Group, 7.5, True),
                      (QgsLegendStyle.Subgroup, 7.5, True), (QgsLegendStyle.SymbolLabel, 7, False)):
        s = lg.style(st)
        s.setTextFormat(tfmt(sz * FS, b))
        if st == QgsLegendStyle.Subgroup:
            s.setMargin(QgsLegendStyle.Bottom, 1.0)
        if st == QgsLegendStyle.SymbolLabel:
            s.setMargin(QgsLegendStyle.Top, 0.8)
            s.setMargin(QgsLegendStyle.Left, 1.5)
        lg.setStyle(st, s)
    lg.setColumnSpace(4)
    lg.setSymbolWidth(sym[0])
    lg.setSymbolHeight(sym[1])
    lg.setColumnCount(cols)
    lg.setBackgroundEnabled(False)
    lg.setFrameEnabled(False)
    lg.attemptMove(QgsLayoutPoint(x, y, MM))
    lg.adjustBoxSize()
    lg.refresh()
    return lg


def scalebar(lay, m, x, y, seg_km, nseg=2, background=True):
    sb = QgsLayoutItemScaleBar(lay)
    lay.addLayoutItem(sb)
    sb.setLinkedMap(m)
    sb.setStyle("Single Box")
    sb.setUnits(QgsUnitTypes.DistanceKilometers)
    sb.setUnitLabel("km")
    sb.setMapUnitsPerScaleBarUnit(1)  # metres -> km conversion is handled by setUnits
    sb.setSegmentSizeMode(Qgis.ScaleBarSegmentSizeMode.Fixed)
    sb.setUnitsPerSegment(seg_km)
    sb.setNumberOfSegments(nseg)
    sb.setNumberOfSegmentsLeft(0)
    sb.setHeight(2.2)
    sb.setTextFormat(tfmt(6.5 * FS))
    sb.setBackgroundEnabled(background)
    sb.setBackgroundColor(QColor(255, 255, 255, 220))
    sb.update()
    sb.resizeToMinimumWidth()
    sb.attemptMove(QgsLayoutPoint(x, y, MM))
    return sb


def north(lay, m, x, y, size=5):
    svg = next(os.path.join(p, "arrows", "NorthArrow_02.svg") for p in QgsApplication.svgPaths()
               if os.path.exists(os.path.join(p, "arrows", "NorthArrow_02.svg")))
    pic = QgsLayoutItemPicture(lay)
    lay.addLayoutItem(pic)
    pic.setPicturePath(svg)
    pic.setLinkedMap(m)
    pic.attemptMove(QgsLayoutPoint(x, y, MM))
    pic.attemptResize(QgsLayoutSize(size, size * 1.3, MM))
    return pic


def new_layout(name):
    lm = P.layoutManager()
    old = lm.layoutByName(name)
    if old:
        lm.removeLayout(old)
    lay = QgsPrintLayout(P)
    lay.initializeDefaults()
    lay.setName(name)
    lay.pageCollection().page(0).setPageSize("Letter", QgsLayoutItemPage.Portrait)
    lm.addLayout(lay)
    return lay


def export(lay, stem):
    os.makedirs(OUTD, exist_ok=True)
    ex = QgsLayoutExporter(lay)
    r1 = ex.exportToPdf(os.path.join(OUTD, stem + ".pdf"), QgsLayoutExporter.PdfExportSettings())
    s = QgsLayoutExporter.ImageExportSettings()
    s.dpi = 300
    r2 = ex.exportToImage(os.path.join(OUTD, stem + ".png"), s)
    return r1, r2


# ---------------------------------------------------------------- layers
lst = raster_copy("B | Mean relative LST (°C vs city median)", "Summer surface temperature vs city median (°C)")
ramp_legend(lst, "−8", "+8")
can = raster_copy("Tree canopy 2021/22 (%)", "Tree canopy, 2021/22 (% of 30 m pixel)")
ramp_legend(can, "0", "100")
chm = raster_copy("Canopy height 1 m (Meta, m)", "Tree canopy height (m)")
ramp_legend(chm, "0", "30")
for lyr in P.mapLayersByName("Tree canopy (grey background)"):
    P.removeMapLayer(lyr)
gry = QgsRasterLayer(can.source(), "Tree canopy (grey background)")
sh = QgsColorRampShader(0, 100, QgsGradientColorRamp(QColor("#ffffff"), QColor("#d0d0d0")))
sh.classifyColorRamp(5)
rs = QgsRasterShader()
rs.setRasterShaderFunction(sh)
gry.setRenderer(QgsSingleBandPseudoColorRenderer(gry.dataProvider(), 1, rs))
P.addMapLayer(gry, False)
grp.addLayer(gry).setItemVisibilityChecked(False)
for n in ("Area shown on page 2", "Zoom areas (pages 2-3)", "Zoom area numbers"):
    for lyr in P.mapLayersByName(n):
        P.removeMapLayer(lyr)
zb = QgsVectorLayer("Polygon?crs=EPSG:32618", "Zoom areas (pages 2-3)", "memory")
znum = QgsVectorLayer("Point?crs=EPSG:32618&field=page:string", "Zoom area numbers", "memory")
for rect, pg in ((ZOOM, "2"), (ZOOM3, "3")):
    f = QgsFeature()
    f.setGeometry(QgsGeometry.fromRect(rect))
    zb.dataProvider().addFeatures([f])
    f = QgsFeature(znum.fields())
    f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(rect.xMinimum() + 250, rect.yMaximum() - 250)))
    f["page"] = pg
    znum.dataProvider().addFeatures([f])
zb.updateExtents()
znum.updateExtents()
zb.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(
    {"color": "0,0,0,0", "outline_color": "0,0,0", "outline_width": "0.5", "outline_style": "dash"})))
znum.setRenderer(QgsSingleSymbolRenderer(QgsMarkerSymbol.createSimple({"size": "0", "color": "0,0,0,0", "outline_style": "no"})))
pal = QgsPalLayerSettings()
pal.fieldName = "page"
pal.placement = Qgis.LabelPlacement.OverPoint
pal.quadOffset = Qgis.LabelQuadrantPosition.BelowRight
tf = tfmt(7 * FS, True, "#000000")
buf = QgsTextBufferSettings()
buf.setEnabled(True)
buf.setSize(0.8)
buf.setColor(QColor("white"))
tf.setBuffer(buf)
pal.setFormat(tf)
znum.setLabeling(QgsVectorLayerSimpleLabeling(pal))
znum.setLabelsEnabled(True)
for lyr in (zb, znum):
    P.addMapLayer(lyr, False)
    grp.addLayer(lyr).setItemVisibilityChecked(False)
for n in ("Open stream channels", "City boundary", "Along-stream forest continuity (%)"):
    grp.findLayer(L(n).id()).setItemVisibilityChecked(False)
streams, city, cont = L("Open stream channels"), L("City boundary"), L("Along-stream forest continuity (%)")
hidden = L("Stream, no visible channel")

CREDIT = ("Data: Landsat 8 (USGS), Jul–Aug 2013–2025, surface (not air) temperature; land cover, streams: "
          "Chesapeake Conservancy / UMBC; canopy height: Meta / WRI. EPSG:32618. Oct 2026.")
CREDIT2 = "Data: USGS Landsat 8; Chesapeake Conservancy / UMBC; Meta / WRI. EPSG:32618. Oct 2026."

# ---------------------------------------------------------------- zoom pages (2, 3): full-bleed panels
PAGE_W, PAGE_H = 215.9, 279.4


def place_in_corner(item, m, corner, inset=1.2, top_inset=None):
    """Move a layout item into a corner of map item m ('tl', 'tr', 'bl', 'br')."""
    item.refresh() if hasattr(item, "refresh") else None
    sz = item.sizeWithUnits()
    mx, my = m.pos().x(), m.pos().y()
    mw, mh = m.sizeWithUnits().width(), m.sizeWithUnits().height()
    x = mx + inset if corner[1] == "l" else mx + mw - sz.width() - inset
    y = my + (inset if top_inset is None else top_inset) if corner[0] == "t" else my + mh - sz.height() - inset
    item.attemptMove(QgsLayoutPoint(x, y, MM))


def stack_next_to(item, base, corner, gap=1.0):
    """Put item directly below (top corners) or above (bottom corners) base, aligned on the corner's side."""
    item.refresh()
    sz, bs = item.sizeWithUnits(), base.sizeWithUnits()
    bx, by = base.pos().x(), base.pos().y()
    x = bx if corner[1] == "l" else bx + bs.width() - sz.width()
    y = by + bs.height() + gap if corner[0] == "t" else by - sz.height() - gap
    item.attemptMove(QgsLayoutPoint(x, y, MM))


def boxed(item):
    item.setBackgroundEnabled(True)
    item.setBackgroundColor(QColor(255, 255, 255, 230))


def zoom_page(name, title, zoom, cap, legend_corner="tr", sb_corner="bl", with_hidden=False):
    lay = new_layout(name)
    GAP, TOP = 3.0, 9.5
    W = (PAGE_W - GAP) / 2  # two full-bleed columns
    H = 121.0
    X = (0, W + GAP)
    Y = (TOP, TOP + H + GAP)
    label(lay, f"<b>{title.upper()}</b>", 0.5, 1.0, PAGE_W - 1, 8, 8 * FS, html=True, color="#1d3f6e")
    lines = [streams, hidden] if with_hidden else [streams]
    line_ents = [(streams, "Open channel"), (hidden, "No visible channel")] if with_hidden else [(streams, "Stream")]
    panels = [("A", "Temperature", lines + [lst], X[0], Y[0], [(lst, "°C vs city median")]),
              ("B", "How much forest", lines + [can], X[1], Y[0], [(can, "Canopy (%)")]),
              ("C", "How tall", lines + [chm], X[0], Y[1], [(chm, "Height (m)")]),
              ("D", "How continuous", [cont] + lines + [gry], X[1], Y[1], [(cont, "")])]
    maps, overlays = [], []
    for letter, ttl, layers, x, y, ents in panels:
        m = mapitem(lay, layers, zoom, x, y, W, H)
        maps.append(m)
        # HTML labels cannot size to their text: estimate width (Arial ~0.5 em per character)
        lab_w = (len(ttl) + 3) * 0.5 * 8 * FS * 0.3528 + 2.5
        lab = label(lay, f"<b>{letter}</b>&nbsp; {ttl}", x + 1.2, y + 1.2, lab_w, 7.6, 8 * FS, html=True)
        boxed(lab)
        lab.setZValue(20)
        if ents[0][0] is cont:
            lg = legend(lay, m, ents, x, y, sym=(3.5, 3.5), cols=3, hide_titles=True)
            lg.setTitle("Canopy along stream (%)")
        else:
            lg = legend(lay, m, ents, x, y, sym=(40, 4.5))
        lg.setBoxSpace(1.5)
        boxed(lg)
        lg.setZValue(20)
        overlays.append((lg, m, legend_corner))
        if letter == "A":  # line symbols in their own small legend, stacked under/over the ramp
            ll = legend(lay, m, line_ents, x, y, sym=(8, 4))
            ll.setBoxSpace(1.5)
            boxed(ll)
            ll.setZValue(20)
            line_legend = (ll, lg)
    sb = scalebar(lay, maps[0], 0, 0, 0.5, 2)
    sb.setBoxContentSpace(1.2)
    sb.setZValue(20)
    na = north(lay, maps[0], 0, 0, 6)
    na.setZValue(20)
    overlays.append((sb, maps[0], sb_corner))
    # item sizes are only known after a first render: render once, then size and place the overlays
    QgsLayoutExporter(lay).renderPageToImage(0, QSize(400, 520))
    for item, m, corner in overlays:
        if isinstance(item, QgsLayoutItemLegend):
            item.adjustBoxSize()
            place_in_corner(item, m, corner, top_inset=10.0)  # top legends clear the panel label
        else:
            place_in_corner(item, m, corner)
    line_legend[0].adjustBoxSize()
    stack_next_to(line_legend[0], line_legend[1], legend_corner)
    stack_next_to(na, sb, sb_corner)  # north arrow sits on top of the scale bar
    y0 = Y[1] + H + 1
    label(lay, cap, 0.5, y0, PAGE_W - 1, PAGE_H - y0 - 7, 7.6 * FS, html=True)
    label(lay, CREDIT2, 0.5, PAGE_H - 6.8, PAGE_W - 1, 6.5, 6.2 * FS, color="#666666", html=True)
    return lay


lay2 = zoom_page("Stream corridors 2 – amount, height, continuity",
                 "Cooler where the forest is bigger, taller and unbroken", ZOOM,
                 "Gwynns Falls (box 2 on page 1). Per +10 points canopy <b>−0.7 °C</b>; per +5 m height <b>−0.6 °C</b>; "
                 "per +10 points canopy along the stream <b>−0.6 °C</b>.",
                 legend_corner="tr", sb_corner="bl")
lay3 = zoom_page("Stream corridors 3 – Jones Falls",
                 "Jones Falls: cool in the park, warm where the forest thins", ZOOM3,
                 "Lower Jones Falls (box 3 on page 1). Coolest in Druid Hill Park's broad, tall forest; warmer along "
                 "the thin strip of trees beside I-83.",
                 legend_corner="bl", sb_corner="br", with_hidden=True)

# ---------------------------------------------------------------- page 1: full-bleed, same treatment as pages 2-3
lay1 = new_layout("Stream corridors 1 – coolest because forested")
GAP1, TOP1, H1 = 3.0, 9.5, 130.0
W1 = (PAGE_W - GAP1) / 2
XL, XR = 0, W1 + GAP1
label(lay1, "<b>BALTIMORE'S COOLEST SURFACES ARE ITS FORESTED STREAM CORRIDORS</b>", 0.5, 1.0, PAGE_W - 1, 8,
      8 * FS, html=True, color="#1d3f6e")
CITY = city.extent()
CITY.grow(250)
mA = mapitem(lay1, [znum, zb, streams, city, lst], CITY, XL, TOP1, W1, H1)
mB = mapitem(lay1, [znum, zb, streams, city, can], CITY, XR, TOP1, W1, H1)
ov1 = []
for m, letter, ttl in ((mA, "A", "Summer surface temperature"), (mB, "B", "Tree canopy")):
    lab_w = (len(ttl) + 3) * 0.5 * 8 * FS * 0.3528 + 2.5
    lab = label(lay1, f"<b>{letter}</b>&nbsp; {ttl}", m.pos().x() + 1.2, TOP1 + 1.2, lab_w, 7.6, 8 * FS, html=True)
    boxed(lab)
    lab.setZValue(20)
    sb = scalebar(lay1, m, 0, 0, 2, 2)
    sb.setBoxContentSpace(1.2)
    sb.setZValue(20)
    na = north(lay1, m, 0, 0, 6)
    na.setZValue(20)
    ov1.append((sb, na, m))
yL = TOP1 + H1 + 1.5  # legend strip under the maps
legend(lay1, mA, [(lst, "°C vs city median")], XL + 0.5, yL, sym=(40, 4.5))
legend(lay1, mA, [(streams, "Stream"), (zb, "Pages 2, 3")], XL + 50, yL + 4, sym=(8, 4))
legend(lay1, mB, [(can, "Canopy (%)")], XR + 0.5, yL, sym=(40, 4.5))
legend(lay1, mB, [(streams, "Stream")], XR + 50, yL + 4, sym=(8, 4))
QgsLayoutExporter(lay1).renderPageToImage(0, QSize(400, 520))  # sizes known after a first render
for sb, na, m in ov1:
    place_in_corner(sb, m, "bl")
    stack_next_to(na, sb, "bl")
yC = yL + 27
label(lay1, "<b>C</b>&nbsp; Corridor temperature by canopy", 0.5, yC, W1, 7.6, 8 * FS, html=True)
pic = QgsLayoutItemPicture(lay1)
lay1.addLayoutItem(pic)
pic.setPicturePath(os.path.join(OUTD, "corridor_lst_by_canopy.png"))
pic.attemptMove(QgsLayoutPoint(XL, yC + 8, MM))
pic.attemptResize(QgsLayoutSize(W1, W1 * 3.27 / 4.19, MM))
cap1 = ("Land within 60 m of a stream is <b>8%</b> of the city but <b>26%</b> of its coolest land.<br><br>"
        "Trees, not water, do the cooling: corridors with over 75% canopy are <b>7.7 °C</b> below the city median; "
        "under 25% canopy, <b>2.7 °C</b>.")
label(lay1, cap1, XR + 0.5, yC + 8, W1 - 1, PAGE_H - yC - 18, 7.6 * FS, html=True)
label(lay1, CREDIT, 0.5, PAGE_H - 13, PAGE_W - 1, 12.5, 6.2 * FS, color="#666666", html=True)

P.write()
print("export p1:", export(lay1, "stream_corridors_p1_coolest_because_forested"))
print("export p2:", export(lay2, "stream_corridors_p2_amount_height_continuity"))
print("export p3:", export(lay3, "stream_corridors_p3_jones_falls"))
