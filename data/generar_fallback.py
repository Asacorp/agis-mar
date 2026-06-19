"""
Genera subareas_fallback.geojson: grilla rectangular del Golfo San Jorge.
Los id_subarea se asignan a las celdas en orden fila-columna (norte a sur, oeste a este)
y tienen que coincidir con los ids del CSV real.
Ejecutar: python data/generar_fallback.py
"""
import json
import math
import pandas as pd

# Bounds del Golfo San Jorge
LAT_NORTE = -45.0
LAT_SUR   = -47.2
LON_OESTE = -68.0
LON_ESTE  = -65.0


def _format_subarea(value) -> str:
    """Mismo formato que core.ingestor._format_subarea (Z01, Z02, ...) para que el
    id_subarea del GeoJSON coincida con el que la app deriva del CSV (sin esto, el
    GeoJSON daria mismatch total contra los ids 'Z01'..'ZNN' del ingestor)."""
    try:
        return f"Z{int(float(value)):02d}"
    except (TypeError, ValueError):
        texto = str(value).strip()
        return texto if texto.upper().startswith("Z") else f"Z_{texto}"


# Leer ids reales del CSV
df = pd.read_csv("data/Reporte_SubAreas_Pesca_2026_2.csv")
# Detectar columna de subarea (puede llamarse sub_area o id_subarea)
col_subarea = next(c for c in df.columns if "sub" in c.lower() or "area" in c.lower())
ids = sorted(df[col_subarea].unique().tolist())
n = len(ids)

# Calcular grilla: más columnas que filas para forma horizontal del golfo
cols = max(2, math.ceil(math.sqrt(n * 1.5)))  # relacion ancho/alto ~1.5
rows = math.ceil(n / cols)

# Tamaño de celda
cell_lat = (LAT_SUR - LAT_NORTE) / rows   # negativo: las celdas bajan de norte a sur
cell_lon = (LON_ESTE - LON_OESTE) / cols

features = []
for i, subarea_id in enumerate(ids):
    row = i // cols
    col = i % cols

    lat_top    = LAT_NORTE + row * cell_lat          # norte de la celda
    lat_bottom = LAT_NORTE + (row + 1) * cell_lat    # sur de la celda
    lon_left   = LON_OESTE + col * cell_lon
    lon_right  = LON_OESTE + (col + 1) * cell_lon

    # Polígono GeoJSON: anillo cerrado, orden lon/lat
    ring = [
        [lon_left,  lat_top],
        [lon_right, lat_top],
        [lon_right, lat_bottom],
        [lon_left,  lat_bottom],
        [lon_left,  lat_top],   # cierre
    ]

    id_fmt = _format_subarea(subarea_id)
    features.append({
        "type": "Feature",
        "properties": {
            "id_subarea": id_fmt,
            "nombre": f"Subárea {id_fmt}",
            "veda": False,
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [ring],
        }
    })

geojson = {"type": "FeatureCollection", "features": features}

with open("data/subareas_fallback.geojson", "w", encoding="utf-8") as f:
    json.dump(geojson, f, ensure_ascii=False, indent=2)

print(f"Generado: {n} subáreas en grilla {rows}x{cols}")
print(f"IDs: {[_format_subarea(i) for i in ids]}")
