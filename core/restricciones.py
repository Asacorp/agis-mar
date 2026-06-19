import pandas as pd
from shapely.geometry import Point, Polygon

VEDA_POLYGONS = [
    {
        "nombre": "AMP Namuncurá (Ley 26.875)",
        "coords": [[-62, -55], [-56, -55], [-56, -53], [-62, -53], [-62, -55]],
    },
    {
        "nombre": "Veda CFP - GSJ Sur",
        "coords": [[-67.5, -47.2], [-65.5, -47.2], [-65.5, -46.4], [-67.5, -46.4], [-67.5, -47.2]],
    },
]


def _ids_en_veda(gdf) -> set:
    """IDs de subárea cuyo centroide cae dentro de algún polígono de veda."""
    polygons = [Polygon(p["coords"]) for p in VEDA_POLYGONS]
    ids = set()
    for _, row in gdf.iterrows():
        centroide = row.geometry.centroid
        punto = Point(centroide.x, centroide.y)
        if any(poly.contains(punto) for poly in polygons):
            ids.add(row["id_subarea"])
    return ids


def apply_restrictions(df: pd.DataFrame, reglas: dict, gdf=None) -> pd.DataFrame:
    """Aplica restricciones normativas/operativas absolutas: prevalecen sobre el ambiente."""
    if df.empty:
        return df

    df = df.copy()
    df["restriccion_motivo"] = ""

    profundidad_max = reglas["batimetria"]["profundidad_max_m"]
    fuera_de_rango = df["batimetria"] > profundidad_max
    df.loc[fuera_de_rango, "restriccion_motivo"] = "Profundidad fuera de rango operativo"
    df.loc[fuera_de_rango, "clasificacion"] = "Restringida"

    if gdf is not None:
        ids = _ids_en_veda(gdf)
        en_veda = df["id_subarea"].isin(ids)
        df.loc[en_veda, "restriccion_motivo"] = "Veda normativa (CFP/AMP)"
        df.loc[en_veda, "clasificacion"] = "Restringida"

    return df
