import pandas as pd


def _impute_with_history(df: pd.DataFrame, col: str) -> pd.Series:
    """Imputa NaN con el promedio histórico de la misma subárea; sin histórico, queda NaN."""
    media_por_subarea = df.groupby("id_subarea")[col].transform("mean")
    return df[col].fillna(media_por_subarea)


def _score_variable(val, min_optimal, max_optimal, weight):
    if pd.isna(val):
        return weight / 2.0  # sin dato ni histórico: score neutral (baja confianza)
    if min_optimal <= val <= max_optimal:
        return weight
    distance = min(abs(val - min_optimal), abs(val - max_optimal))
    penalty = distance * (weight / 5.0)
    return max(0.0, weight - penalty)


def process_diagnostics(df: pd.DataFrame, reglas: dict) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    tsm_imputado = _impute_with_history(df, "tsm")
    clorofila_imputado = _impute_with_history(df, "clorofila")
    df["baja_confianza"] = tsm_imputado.isna() | clorofila_imputado.isna()

    tsm_cfg = reglas["variables"]["tsm"]
    clorofila_cfg = reglas["variables"]["clorofila"]

    tsm_score = tsm_imputado.apply(
        lambda v: _score_variable(v, tsm_cfg["min_optimal"], tsm_cfg["max_optimal"], tsm_cfg["weight"])
    )
    clorofila_score = clorofila_imputado.apply(
        lambda v: _score_variable(v, clorofila_cfg["min_optimal"], clorofila_cfg["max_optimal"], clorofila_cfg["weight"])
    )
    df["score_ambiental"] = (tsm_score + clorofila_score).round(1)

    recomendada_min = reglas["thresholds"]["recomendada_min"]
    con_reserva_min = reglas["thresholds"]["con_reserva_min"]

    def clasificar(score):
        if score >= recomendada_min: return "Recomendada"
        elif score >= con_reserva_min: return "Con reserva"
        else: return "Restringida"

    df["clasificacion"] = df["score_ambiental"].apply(clasificar)
    return df
