
import hashlib
import random

from .db import conectar, inserir_varios

CATEGORIAS = ["buraco", "obstaculo", "falta_rampa", "iluminacao_apagada", "obra", "alagamento"]
PESOS = [34, 24, 12, 12, 10, 8]           # buraco é o problema mais comum em calçada
USUARIOS = [f"sim_{i:03d}" for i in range(1, 61)]


def simular(semente, novos_relatos=8):
    rng = random.Random(semente)            # mesma semente = mesmos dados (reprodutível)
    with conectar() as conn, conn.cursor() as cur:
        # 1) sorteia pontos ao longo de trechos reais do grafo
        cur.execute("""
            SELECT ST_Y(p), ST_X(p) FROM (
              SELECT ST_LineInterpolatePoint(geom, 0.5) AS p FROM gold.trechos
              ORDER BY random() LIMIT %s) x""", (novos_relatos,))
        pontos = cur.fetchall()
        for lat, lon in pontos:
            cur.execute("""
                INSERT INTO app.relatos (usuario_hash, categoria, lat, lon, simulado)
                VALUES (%s, %s, %s, %s, true)""",
                (rng.choice(USUARIOS), rng.choices(CATEGORIAS, PESOS)[0], lat, lon))

        # 2) outras pessoas passam pelos relatos dos últimos 3 dias e respondem
        cur.execute("SELECT relato_id FROM app.relatos WHERE criado_em > now() - interval '3 days'")
        respostas = []
        for (relato_id,) in cur.fetchall():
            # 85% dos relatos são reais; a "verdade" sai do próprio id, então é sempre a mesma
            verdadeiro = int(hashlib.md5(str(relato_id).encode()).hexdigest(), 16) % 100 < 85
            for _ in range(rng.randint(0, 2)):
                acerta = rng.random() < 0.9                       # as pessoas às vezes se enganam
                existe = verdadeiro if acerta else not verdadeiro
                respostas.append((relato_id, rng.choice(USUARIOS), "ainda_esta" if existe else "nao_tem"))
        inserir_varios(cur, "INSERT INTO app.confirmacoes (relato_id, usuario_hash, resposta) VALUES %s", respostas)
    print(f"Simulados {len(pontos)} relatos e {len(respostas)} respostas")
    return {"relatos": len(pontos), "respostas": len(respostas)}