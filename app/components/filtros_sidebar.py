import streamlit as st
import pandas as pd
from core.ingestor import load_config
from app.components.mapa import _WMS_LAYERS

_ETIQUETAS = {"recomendada": "Recomendada", "con_reserva": "Con reserva", "restringida": "Restringida"}


def render(df: pd.DataFrame):
    st.sidebar.header("Filtros")

    periodos = sorted(df["periodo"].unique().tolist(), reverse=True)
    selected_periodo = st.sidebar.selectbox("Período de análisis", periodos)

    zonas = sorted(df["id_subarea"].unique().tolist())
    selected_subarea = st.sidebar.selectbox("Subárea (tendencia histórica)", zonas)

    df_periodo = df[df["periodo"] == selected_periodo]

    clasificaciones = sorted(df_periodo["clasificacion"].unique().tolist())
    seleccionadas = st.sidebar.multiselect("Clasificación", options=clasificaciones, default=clasificaciones)

    st.sidebar.markdown("---")
    wms_layer_key = st.sidebar.selectbox(
        "Capa satelital (fondo)",
        options=list(_WMS_LAYERS.keys()),
        index=0,
    )

    settings = load_config("config/settings.yaml")

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Leyenda**")
    for clave, color in settings["colores"].items():
        etiqueta = _ETIQUETAS.get(clave, clave)
        st.sidebar.markdown(
            f"<span style='display:inline-block;width:12px;height:12px;"
            f"background-color:{color};border-radius:2px;margin-right:6px;'></span>{etiqueta}",
            unsafe_allow_html=True,
        )

    st.sidebar.markdown("---")
    st.sidebar.caption(settings["app"]["fuente_datos"])

    if seleccionadas:
        df_filtrado = df_periodo[df_periodo["clasificacion"].isin(seleccionadas)]
    else:
        df_filtrado = df_periodo.iloc[0:0]

    return df_filtrado, selected_subarea, wms_layer_key
