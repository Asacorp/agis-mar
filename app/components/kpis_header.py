import streamlit as st
import pandas as pd
from core.ingestor import load_config


def render(df: pd.DataFrame):
    if df.empty:
        st.info("Sin datos para mostrar KPIs.")
        return

    settings = load_config("config/settings.yaml")
    colores = settings["colores"]

    total = len(df)
    recomendadas = int((df["clasificacion"] == "Recomendada").sum())
    con_reserva = int((df["clasificacion"] == "Con reserva").sum())
    restringidas = int((df["clasificacion"] == "Restringida").sum())
    baja_confianza = int(df["baja_confianza"].sum()) if "baja_confianza" in df.columns else 0

    pct_rec = f"{recomendadas/total*100:.0f}%" if total else "—"
    pct_res = f"{restringidas/total*100:.0f}%" if total else "—"

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Zonas analizadas", total)
    c2.metric("Recomendadas", recomendadas, delta=pct_rec, delta_color="off")
    c3.metric("Con reserva", con_reserva)
    c4.metric("Restringidas", restringidas, delta=pct_res, delta_color="off")
    c5.metric("Baja confianza", baja_confianza, delta="datos imputados" if baja_confianza else None, delta_color="inverse")

    # Alertas activas
    if baja_confianza > 0:
        st.warning(f"⚠️ {baja_confianza} zona(s) con datos imputados por ausencia de lectura directa. Interpretá el score con precaución.")

    zonas_vedadas = df[df["restriccion_motivo"].str.contains("Veda", na=False)]["id_subarea"].tolist() if "restriccion_motivo" in df.columns else []
    if zonas_vedadas:
        st.error(f"🚫 Veda normativa activa en: {', '.join(zonas_vedadas)}")

    st.markdown("---")
