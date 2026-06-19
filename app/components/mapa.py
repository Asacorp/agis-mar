import json
import math
import pydeck as pdk
import streamlit as st
import pandas as pd
from core.ingestor import load_config
from core.restricciones import VEDA_POLYGONS

MAP_HEIGHT = 600

_WMS_BASE = "https://geoservicios2.conae.gov.ar/geoserver/AplicacionesMarinas/wms"
_WMS_LAYERS = {
    "Clorofila (VIIRS)": "Pesca:SNPP_VIIRS_CHLA_1",
    "TSM diurna (VIIRS)": "Pesca:SNPP_VIIRS_SST_1",
    "Esfuerzo pesquero (GFW)": "Pesca:GFW_AIS_EPA_1",
}
_GSJ_BBOX = [-68.0, -47.2, -65.0, -45.0]  # [west, south, east, north]

# Caja aproximada de aguas abiertas para la grilla inventada cuando no hay GeoJSON
# con polígonos reales (Golfo San Jorge y adyacencias).
_LAT_NORTE, _LAT_SUR = -45.6, -47.2
_LON_ESTE, _LON_OESTE = -65.4, -66.9


def _linspace(start, stop, n):
    if n <= 1:
        return [(start + stop) / 2]
    step = (stop - start) / (n - 1)
    return [start + i * step for i in range(n)]


def _build_grid(zonas: list) -> dict:
    """Posición fija por zona, en grilla cuadrada, estable ante cambios de filtro."""
    n = len(zonas)
    if n == 0:
        return {}
    cols = max(1, math.ceil(math.sqrt(n)))
    rows = max(1, math.ceil(n / cols))
    lat_vals = _linspace(_LAT_NORTE, _LAT_SUR, rows)
    lon_vals = _linspace(_LON_ESTE, _LON_OESTE, cols)
    return {
        zid: (lat_vals[idx // cols], lon_vals[idx % cols])
        for idx, zid in enumerate(sorted(zonas))
    }


def _hex_to_rgba(hex_color: str, alpha: int = 200):
    h = hex_color.lstrip("#")
    return [int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha]


def _color_map(colores: dict) -> dict:
    return {
        "Recomendada": _hex_to_rgba(colores["recomendada"]),
        "Con reserva": _hex_to_rgba(colores["con_reserva"]),
        "Restringida": _hex_to_rgba(colores["restringida"]),
    }


def _tooltip():
    return {
        "html": "<b>Zona:</b> {id_subarea}<br/>"
                "<b>TSM:</b> {tsm} °C<br/>"
                "<b>Clorofila:</b> {clorofila}<br/>"
                "<b>Profundidad:</b> {batimetria} m<br/>"
                "<b>Score:</b> {score_ambiental}<br/>"
                "<b>Clasificación:</b> {clasificacion}"
    }


def _build_wms_layer(layer_key: str):
    oeste, sur, este, norte = _GSJ_BBOX
    url = (
        f"{_WMS_BASE}?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap"
        f"&FORMAT=image/png&TRANSPARENT=true"
        f"&LAYERS={_WMS_LAYERS[layer_key]}"
        f"&BBOX={oeste},{sur},{este},{norte}"
        f"&WIDTH=512&HEIGHT=512&SRS=EPSG:4326"
    )
    return pdk.Layer("BitmapLayer", data=None, image=url, bounds=_GSJ_BBOX, opacity=0.75)


def _build_veda_layer():
    veda_data = [{"polygon": p["coords"], "nombre": p["nombre"]} for p in VEDA_POLYGONS]
    return pdk.Layer(
        "PolygonLayer",
        data=veda_data,
        get_polygon="polygon",
        get_fill_color=[255, 0, 0, 55],
        get_line_color=[220, 0, 0, 200],
        line_width_min_pixels=2,
        pickable=False,
    )


def _render_deck(layers: list, view_state):
    r = pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        tooltip=_tooltip(),
        map_provider="carto",
        map_style="light",
    )
    st.pydeck_chart(r, height=MAP_HEIGHT)


def render(df: pd.DataFrame, gdf=None, wms_layer_key: str = "Clorofila (VIIRS)"):
    st.subheader("Mapa de Prioridades")
    if df.empty:
        st.info("Sin datos para renderizar el mapa.")
        return

    colores = load_config("config/settings.yaml")["colores"]
    color_por_clasificacion = _color_map(colores)

    if gdf is not None:
        plot_gdf = gdf.merge(df, on="id_subarea")
        if plot_gdf.empty:
            st.warning("Las subáreas del GeoJSON no coinciden con las del CSV; no se puede dibujar el mapa.")
            return
        plot_gdf["fill_color"] = plot_gdf["clasificacion"].map(color_por_clasificacion)
        geojson_data = json.loads(plot_gdf.to_json())

        data_layer = pdk.Layer(
            "GeoJsonLayer",
            geojson_data,
            opacity=0.8,
            stroked=True,
            filled=True,
            extruded=False,
            get_fill_color="properties.fill_color",
            get_line_color=[255, 255, 255],
            pickable=True,
        )
        view_state = pdk.ViewState(latitude=-46.4, longitude=-66.15, zoom=5.5)
    else:
        zonas_totales = st.session_state.get("zonas_totales") or sorted(df["id_subarea"].unique().tolist())
        posiciones = _build_grid(zonas_totales)

        plot_df = df.copy()
        plot_df[["lat", "lon"]] = plot_df["id_subarea"].map(posiciones).apply(pd.Series)
        plot_df["color"] = plot_df["clasificacion"].map(color_por_clasificacion)

        data_layer = pdk.Layer(
            "ScatterplotLayer",
            plot_df,
            get_position=["lon", "lat"],
            get_fill_color="color",
            get_radius=25000,
            opacity=0.85,
            stroked=True,
            get_line_color=[255, 255, 255],
            pickable=True,
        )
        view_state = pdk.ViewState(latitude=-46.4, longitude=-66.15, zoom=6.5)

    layers = [_build_wms_layer(wms_layer_key), _build_veda_layer(), data_layer]
    _render_deck(layers, view_state)
