import sys
import os

# Aseguramos que el root del proyecto esté en el path para las importaciones de 'core'
root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

import streamlit as st
from core.ingestor import load_data, load_geojson, load_config, find_subarea_mismatch
from core.diagnostico import process_diagnostics
from core.restricciones import apply_restrictions
from app.components import kpis_header, filtros_sidebar, mapa, tabla_detalle

st.set_page_config(page_title="AGIS Mar", layout="wide")

COLUMNAS_CONFIG = "config/columnas.yaml"


def _resolve_sources(settings: dict, uploaded_csv, uploaded_geojson):
    """Si falta una de las dos cargas, se completa con el archivo sintético de fallback local."""
    csv_fallback = settings["data_paths"]["csv_fallback"]
    geojson_fallback = settings["data_paths"]["geojson_fallback"]
    csv_real = settings["data_paths"]["csv_real"]

    if uploaded_csv is not None and uploaded_geojson is not None:
        return uploaded_csv, uploaded_geojson
    if uploaded_csv is not None:
        st.sidebar.info("No subiste GeoJSON: se completa con el de fallback sintético para el mapa.")
        return uploaded_csv, geojson_fallback
    if uploaded_geojson is not None:
        st.sidebar.info("No subiste CSV: se completa con el CSV de fallback sintético.")
        return csv_fallback, uploaded_geojson
    return csv_real, None


def main():
    settings = load_config("config/settings.yaml")
    reglas = load_config("config/reglas.yaml")

    st.title(settings["app"]["titulo"])
    st.caption(settings["app"]["subtitulo"])

    st.sidebar.header("Carga de Datos")
    uploaded_csv = st.sidebar.file_uploader("CSV de subáreas", type=["csv"])
    uploaded_geojson = st.sidebar.file_uploader("GeoJSON de subáreas (opcional)", type=["geojson", "json"])
    csv_source, geojson_source = _resolve_sources(settings, uploaded_csv, uploaded_geojson)

    df = load_data(csv_source, COLUMNAS_CONFIG)
    gdf = load_geojson(geojson_source, COLUMNAS_CONFIG)

    filas_sin_fecha = df["periodo"].isna().sum()
    if filas_sin_fecha > 0:
        st.warning(f"⚠️ {filas_sin_fecha} fila(s) descartadas por fecha no reconocida en el CSV.")
    df = df.dropna(subset=["periodo"])

    if df.empty:
        st.error(
            "⚠️ No quedaron lecturas con fecha válida tras la carga. Revisá el formato de la "
            "columna de fecha en el CSV (se aceptan fechas simples y rangos como "
            "'2026-01-01 a 2026-01-31')."
        )
        st.stop()

    if uploaded_csv is not None:
        st.sidebar.success(f"✅ {len(df)} lecturas detectadas en el CSV subido.")
    if uploaded_geojson is not None and gdf is not None:
        st.sidebar.success(f"✅ {len(gdf)} subáreas detectadas en el GeoJSON subido.")
    st.sidebar.markdown("---")

    if gdf is not None:
        total_zonas_csv = df["id_subarea"].nunique()
        mismatches = find_subarea_mismatch(df, gdf)
        if mismatches and len(mismatches) == total_zonas_csv:
            st.error(
                "⚠️ Ninguna subárea del CSV coincide con el GeoJSON cargado. Verificá que ambos "
                "archivos correspondan al mismo set de subáreas del CFP. El mapa muestra una "
                "grilla de respaldo mientras se resuelve la incompatibilidad."
            )
            gdf = None
        elif mismatches:
            st.warning(f"⚠️ {len(mismatches)} subárea(s) del CSV sin polígono en el GeoJSON: {mismatches}")

    df = process_diagnostics(df, reglas)
    df = apply_restrictions(df, reglas, gdf)
    st.session_state["zonas_totales"] = sorted(df["id_subarea"].unique().tolist())

    df_filtrado, selected_subarea, wms_layer_key = filtros_sidebar.render(df)

    kpis_header.render(df_filtrado)
    col_mapa, col_tabla = st.columns([3, 2])
    with col_mapa: mapa.render(df_filtrado, gdf, wms_layer_key)
    with col_tabla: tabla_detalle.render(df_filtrado)

    tab1, tab2 = st.tabs(["Evolución Temporal", "Comparativa de Subáreas"])

    with tab1:
        st.subheader("Tendencia Ambiental")
        df_historico = df[df["id_subarea"] == selected_subarea][["periodo", "tsm", "clorofila"]].melt(
            id_vars="periodo", var_name="variable", value_name="valor"
        )
        if df_historico.empty:
            st.info("No hay lecturas históricas para la subárea seleccionada.")
        else:
            st.line_chart(data=df_historico, x="periodo", y="valor", color="variable")

    with tab2:
        st.subheader("Comparativa de Subáreas")
        if df_filtrado.empty:
            st.info("No hay datos para comparar en el período seleccionado.")
        else:
            df_scores = df_filtrado[["id_subarea", "score_ambiental"]].sort_values("score_ambiental")
            st.bar_chart(data=df_scores, x="id_subarea", y="score_ambiental", horizontal=True)

    st.markdown("---")
    st.caption(settings["app"]["disclaimer"])


main()
