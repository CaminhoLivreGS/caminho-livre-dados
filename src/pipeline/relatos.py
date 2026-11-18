
from datetime import timedelta

import pandas as pd

from .db import conectar

VALIDADE = {   # quanto tempo o aviso vale sem ninguém confirmar de novo
    "alagamento": timedelta(hours=6),
    "obstaculo": timedelta(hours=48),
    "buraco": timedelta(days=30),
    "iluminacao_apagada": timedelta(days=15),
    "obra": timedelta(days=60),
    "falta_rampa": timedelta(days=180),
}
MIN_PESSOAS = 3      # pessoas diferentes, contando quem relatou
MIN_NEGATIVAS = 2


def extrair():
    """Lê do banco do app tudo o que pode mudar de status (últimos 200 dias)."""
    with conectar() as conn:
        relatos = pd.read_sql("""SELECT relato_id::text, usuario_hash, categoria, lat, lon, criado_em
                                 FROM app.relatos WHERE criado_em > now() - interval '200 days'""", conn)
        respostas = pd.read_sql("""SELECT relato_id::text, usuario_hash, resposta, criado_em
                                   FROM app.confirmacoes""", conn)
    return relatos, respostas


def limpar(relatos, bbox):
    """Tira relatos fora do bairro, com categoria desconhecida ou repetidos."""
    s, w, n, e = bbox
    antes = len(relatos)
    r = relatos[relatos["categoria"].isin(VALIDADE)]
    r = r[r["lat"].between(s, n) & r["lon"].between(w, e)]
    r = r.drop_duplicates(subset=["usuario_hash", "categoria", "lat", "lon"])
    print(f"Limpeza: {antes} relatos → {len(r)} válidos")
    return r


def consolidar(relatos, respostas, agora):
    linhas = []
    for r in relatos.itertuples():
        resp = respostas[(respostas["relato_id"] == r.relato_id) & (respostas["usuario_hash"] != r.usuario_hash)]
        resp = resp.sort_values("criado_em").drop_duplicates("usuario_hash", keep="last")  # vale a última resposta de cada um
        sim = resp[resp["resposta"] == "ainda_esta"]
        nao = resp[resp["resposta"] == "nao_tem"]
        pessoas_sim = 1 + len(sim)                       # quem relatou conta como 1
        ultima = max([r.criado_em] + list(sim["criado_em"]))
        valido_ate = ultima + VALIDADE[r.categoria]

        if len(nao) >= MIN_NEGATIVAS and len(nao) >= len(sim):
            status = "descartado"
        elif agora > valido_ate:
            status = "descartado"                        # expirou sem nova confirmação
        elif pessoas_sim >= MIN_PESSOAS:
            status = "confirmado"
        elif len(resp) > 0:
            status = "em_verificacao"
        else:
            status = "novo"
        linhas.append({"relato_id": r.relato_id, "categoria": r.categoria, "status": status,
                       "pessoas_confirmaram": pessoas_sim, "pessoas_negaram": len(nao),
                       "criado_em": r.criado_em, "valido_ate": valido_ate if status != "descartado" else None,
                       "lat": r.lat, "lon": r.lon})
    df = pd.DataFrame(linhas)
    print(df["status"].value_counts().to_dict() if not df.empty else "sem relatos")
    return df