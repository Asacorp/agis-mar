import io
import streamlit as st
import pandas as pd


def render(df: pd.DataFrame):
    st.subheader("Detalle Operativo")
    if df.empty:
        st.info("No hay datos en la tabla.")
        return

    display_df = df[[
        "id_subarea", "tsm", "clorofila", "batimetria",
        "score_ambiental", "clasificacion", "restriccion_motivo", "baja_confianza",
    ]].sort_values("score_ambiental", ascending=False).copy()

    display_df["baja_confianza"] = display_df["baja_confianza"].map({True: "⚠️ Sí", False: ""})

    display_df.rename(columns={
        "id_subarea": "Zona", "tsm": "TSM (°C)", "clorofila": "Clorofila",
        "batimetria": "Profundidad (m)", "score_ambiental": "Score (0-100)",
        "clasificacion": "Clasificación", "restriccion_motivo": "Restricción",
        "baja_confianza": "Baja Confianza",
    }, inplace=True)

    display_df["TSM (°C)"] = display_df["TSM (°C)"].round(1)
    display_df["Clorofila"] = display_df["Clorofila"].round(4)
    display_df["Profundidad (m)"] = display_df["Profundidad (m)"].round(0).astype(int)
    display_df["Score (0-100)"] = display_df["Score (0-100)"].round(1)

    st.caption(f"{len(display_df)} zona(s) en el período seleccionado")
    st.dataframe(display_df, use_container_width=True, hide_index=True, height=400)

    buffer = io.BytesIO()
    display_df.to_excel(buffer, index=False, engine="openpyxl")
    st.download_button(
        "Descargar Excel",
        data=buffer.getvalue(),
        file_name="agis_mar_reporte.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
