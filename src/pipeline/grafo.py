#Pega os dados em JSON da API OpenStreetMap, separa as ruas em pedaços menores, e cada pedaço ganha as informações necessarias para os pedestres que possuedm dificuldades de locomoção.
import time
from collections import Counter

import pandas as pd
import requests
from pyproj import Geod

from . import config

GEOD = Geod(ellps="WGS84")  # para medir distâncias em metros sobre a Terra
PISOS_RUINS = {"unpaved", "gravel", "dirt", "ground", "sand", "grass", "sett", "cobblestone", "compacted"}


def _sim_nao(valor):
    
    if valor in ("yes", "designated"):
        return True
    if valor == "no":
        return False
    return None


def _calcada(tags):
    if tags["highway"] in ("footway", "pedestrian", "path", "steps", "living_street"):
        return "exclusiva"
    s = tags.get("sidewalk")
    if s == "both":
        return "ambos"
    if s in ("left", "right"):
        return "um_lado"
    if s in ("no", "none"):
        return "nao"
    return "sem_dado"


def construir(osm):
    """Devolve três tabelas: nos (pontas dos trechos), trechos e equipamentos."""
    nos = {e["id"]: e for e in osm["elements"] if e["type"] == "node"}
    vias = [e for e in osm["elements"] if e["type"] == "way" and "highway" in e.get("tags", {})]

    # Um nó vira ponta de trecho quando é início/fim de via, é usado por 2+ vias
    # (cruzamento) ou tem informação de travessia ou guia.
    uso = Counter(n for v in vias for n in v["nodes"])

    def eh_ponta(nid, i, total):
        t = nos.get(nid, {}).get("tags", {})
        return i in (0, total - 1) or uso[nid] > 1 or t.get("highway") == "crossing" or "kerb" in t

    trechos, pontas = [], set()
    for via in vias:
        tags = via["tags"]
        ids = [n for n in via["nodes"] if n in nos]
        inicio = 0
        for i in range(1, len(ids)):
            if not eh_ponta(ids[i], i, len(ids)):
                continue
            pedaco, inicio = ids[inicio:i + 1], i
            lons = [nos[n]["lon"] for n in pedaco]
            lats = [nos[n]["lat"] for n in pedaco]
            comprimento = GEOD.line_length(lons, lats)
            if comprimento < 0.5:
                continue
            tags_nos = [nos[n].get("tags", {}) for n in pedaco]
            guias = [t["kerb"] in ("lowered", "flush", "no") for t in tags_nos if "kerb" in t]
            superficie = tags.get("surface") or tags.get("sidewalk:surface")
            trechos.append({
                "osm_way_id": via["id"],
                "no_origem": pedaco[0],
                "no_destino": pedaco[-1],
                "nome_via": tags.get("name"),
                "tipo_via": tags["highway"],
                "comprimento_m": round(comprimento, 2),
                "tem_escada": tags["highway"] == "steps",
                "calcada": _calcada(tags),
                "superficie_ruim": (superficie in PISOS_RUINS) if superficie else None,
                "iluminado": _sim_nao(tags.get("lit")),
                "travessia": any(t.get("highway") == "crossing" for t in tags_nos) or tags.get("footway") == "crossing",
                "guia_rebaixada": all(guias) if guias else None,
                "piso_tatil": _sim_nao(tags.get("tactile_paving")),
                "geom_wkt": "LINESTRING(" + ", ".join(f"{lo} {la}" for lo, la in zip(lons, lats)) + ")",
            })
            pontas.update((pedaco[0], pedaco[-1]))

    df_trechos = pd.DataFrame(trechos)
    df_trechos.insert(0, "id", range(1, len(df_trechos) + 1))
    df_nos = pd.DataFrame([{"id": n, "lat": nos[n]["lat"], "lon": nos[n]["lon"]} for n in sorted(pontas)])

    equipamentos = []
    for nid, no in nos.items():
        t = no.get("tags", {})
        categoria = (
            "saude" if t.get("amenity") in ("clinic", "doctors", "hospital") else
            "escola" if t.get("amenity") == "school" else
            "estacao" if t.get("railway") == "station" else
            "ponto_onibus" if t.get("highway") == "bus_stop" else
            "farmacia" if t.get("amenity") == "pharmacy" else None
        )
        if categoria:
            equipamentos.append({"osm_id": nid, "categoria": categoria, "nome": t.get("name"), "lat": no["lat"], "lon": no["lon"]})
    df_equip = pd.DataFrame(equipamentos, columns=["osm_id", "categoria", "nome", "lat", "lon"])
    return df_nos, df_trechos, df_equip


def buscar_altitude(df_nos):
    """Pergunta a altitude de cada nó para a OpenTopoData (100 pontos por vez, 1 pedido por segundo)."""
    resultados = []
    for i in range(0, len(df_nos), 100):
        lote = df_nos.iloc[i:i + 100]
        locais = "|".join(f"{la:.6f},{lo:.6f}" for la, lo in zip(lote["lat"], lote["lon"]))
        resp = requests.get(config.ELEVACAO_URL, params={"locations": locais}, timeout=60)
        resp.raise_for_status()
        for nid, r in zip(lote["id"], resp.json()["results"]):
            resultados.append({"no_id": int(nid), "elevacao_m": r["elevation"]})
        time.sleep(1.1)
    return resultados


def calcular_inclinacao(df_trechos, altitudes):
    """Inclinação (%) = diferença de altura entre as pontas / comprimento x 100."""
    alt = {a["no_id"]: a["elevacao_m"] for a in altitudes}
    t = df_trechos.copy()

    def inclinacao(linha):
        h1, h2 = alt.get(linha["no_origem"]), alt.get(linha["no_destino"])
        if h1 is None or h2 is None or linha["comprimento_m"] < 30:
          return None
        return round(abs(h2 - h1) / linha["comprimento_m"] * 100, 2)

    t["inclinacao_pct"] = t.apply(inclinacao, axis=1)
    return t


def calcular_completude(df_trechos):
    """Quanto do trecho está mapeado, de 0 a 1. Abaixo de 0,5 o app avisa 'trecho sem dado'."""
    campos = ["superficie_ruim", "iluminado", "inclinacao_pct"]
    conhecidos = df_trechos[campos].notna().sum(axis=1) + (df_trechos["calcada"] != "sem_dado")
    return (conhecidos / (len(campos) + 1)).round(2)