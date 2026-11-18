
import pandas as pd
import requests

from . import config


def baixar():
    s, w, n, e = config.BBOX
    resp = requests.get(config.CHUVA_URL, params={
        "latitude": (s + n) / 2, "longitude": (w + e) / 2,
        "hourly": "precipitation", "forecast_days": 2, "timezone": "America/Sao_Paulo",
    }, timeout=60)
    resp.raise_for_status()
    return resp.json()


def intensidade(mm):

    if mm is None or mm < 0.1:
        return "nenhuma"
    if mm < 2.5:
        return "fraca"
    if mm <= 7.6:
        return "moderada"
    return "forte"


def transformar(dados):
    df = pd.DataFrame({
        "hora": pd.to_datetime(dados["hourly"]["time"]).tz_localize("America/Sao_Paulo"),
        "precipitacao_mm": dados["hourly"]["precipitation"],
    })
    df["intensidade"] = df["precipitacao_mm"].map(intensidade)
    return df