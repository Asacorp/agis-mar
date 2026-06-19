import pandas as pd
import geopandas as gpd
import yaml
import streamlit as st
import os

FUENTE = "MODIS-Aqua L3SMI / GEBCO (GEE)"
REQUIRED_FIELDS = ["fecha", "subarea", "tsm", "clorofila", "batimetria"]


def _label(source) -> str:
    """Nombre legible de la fuente (ruta local o archivo subido) para mensajes de error."""
    return source if isinstance(source, str) else getattr(source, "name", "archivo subido")


@st.cache_data
def load_config(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        st.error(f"Error cargando configuración {path}: {e}")
        st.stop()


def _resolve_columns(columns, columnas_cfg: dict) -> dict:
    """Mapea cada campo lógico a una columna real: nombre exacto primero, sino keywords."""
    available = list(columns)
    resolved = {}
    for field, spec in columnas_cfg["columnas_csv"].items():
        match = None
        nombre_exacto = spec.get("nombre_exacto")
        if nombre_exacto:
            match = next((c for c in available if c.lower() == nombre_exacto.lower()), None)
        if not match:
            for kw in spec.get("keywords", []):
                match = next((c for c in available if kw in c.lower()), None)
                if match:
                    break
        if match:
            resolved[field] = match
            available.remove(match)
    return resolved


def _format_subarea(value) -> str:
    try:
        return f"Z{int(float(value)):02d}"
    except (TypeError, ValueError):
        texto = str(value).strip()
        return texto if texto.upper().startswith("Z") else f"Z_{texto}"


def _parse_fecha_robusta(serie: pd.Series) -> pd.Series:
    """Intenta múltiples formatos de fecha. Retorna NaT para valores no parseables."""
    formatos = [
        "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y",
        "%Y-%m", "%m/%Y", "%Y%m%d",
    ]
    # Rangos tipo "2026-01-01 a 2026-01-31" o "2026-01-01 - 2026-01-31":
    # nos quedamos con la fecha de inicio del período.
    serie = (
        serie.astype("string")
        .str.split(r"\s+(?:a|al|-|–|hasta|to)\s+", n=1, regex=True)
        .str[0]
        .str.strip()
    )
    resultado = pd.to_datetime(serie, errors="coerce")
    if resultado.isna().all():
        for fmt in formatos:
            try:
                resultado = pd.to_datetime(serie, format=fmt, errors="coerce")
                if resultado.notna().any():
                    break
            except Exception:
                continue
    return resultado


@st.cache_data
def load_data(source, config_path: str) -> pd.DataFrame:
    """Carga lecturas desde una ruta local o un CSV subido, tolerando variaciones de columnas y NaN."""
    columnas_cfg = load_config(config_path)

    if isinstance(source, str) and not os.path.exists(source):
        st.error(f"⚠️ No se encontró el archivo de datos: {source}")
        st.stop()

    try:
        if hasattr(source, "seek"):
            source.seek(0)
        raw = pd.read_csv(source)
    except Exception as e:
        st.error(f"⚠️ Error leyendo el CSV ({_label(source)}): {e}")
        st.stop()

    resolved = _resolve_columns(raw.columns, columnas_cfg)
    faltantes = [f for f in REQUIRED_FIELDS if f not in resolved]
    if faltantes:
        st.error(
            f"⚠️ No se pudieron identificar en el CSV ({_label(source)}) las columnas para: {faltantes}. "
            f"Columnas disponibles: {list(raw.columns)}"
        )
        st.stop()

    fecha = _parse_fecha_robusta(raw[resolved["fecha"]])
    periodo = fecha.dt.to_period("M").astype(str)
    periodo[fecha.isna()] = None

    df = pd.DataFrame({
        "periodo": periodo,
        "id_subarea": raw[resolved["subarea"]].apply(_format_subarea),
        "tsm": pd.to_numeric(raw[resolved["tsm"]], errors="coerce"),
        "clorofila": pd.to_numeric(raw[resolved["clorofila"]], errors="coerce"),
        "batimetria": pd.to_numeric(raw[resolved["batimetria"]], errors="coerce").abs(),
    })
    if "semaforo" in resolved:
        df["semaforo_raw"] = pd.to_numeric(raw[resolved["semaforo"]], errors="coerce")
    df["fuente"] = FUENTE

    n_nan_tsm = int(df["tsm"].isna().sum())
    n_nan_clorofila = int(df["clorofila"].isna().sum())
    if n_nan_tsm or n_nan_clorofila:
        st.warning(
            f"⚠️ Datos faltantes detectados (TSM: {n_nan_tsm}, Clorofila: {n_nan_clorofila}). "
            "Se imputan con el promedio histórico de cada subárea; si no hay histórico, se usa "
            "un score neutral marcado como baja confianza."
        )

    return df


@st.cache_data
def load_geojson(source, config_path: str):
    """Carga polígonos reales de subáreas (opcional). Devuelve None si no hay fuente disponible."""
    if source is None:
        return None
    if isinstance(source, str) and not os.path.exists(source):
        return None

    columnas_cfg = load_config(config_path)
    try:
        if hasattr(source, "seek"):
            source.seek(0)
        gdf = gpd.read_file(source)
    except Exception as e:
        st.error(f"⚠️ Error leyendo el GeoJSON ({_label(source)}): {e}")
        st.stop()

    faltantes = [c for c in columnas_cfg["geojson_properties"] if c not in gdf.columns]
    if faltantes:
        st.error(f"⚠️ Faltan propiedades requeridas en el GeoJSON ({_label(source)}): {faltantes}")
        st.stop()

    gdf["id_subarea"] = gdf["id_subarea"].astype(str)
    return gdf


def find_subarea_mismatch(df: pd.DataFrame, gdf) -> list:
    """IDs de subárea presentes en el CSV sin contraparte en el GeoJSON (lista vacía si no hay GeoJSON)."""
    if gdf is None:
        return []
    return sorted(set(df["id_subarea"].unique()) - set(gdf["id_subarea"].unique()))
