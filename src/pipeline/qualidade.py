"""Checagens de qualidade. Se uma regra crítica falha, a tarefa falha e o Airflow mostra em vermelho."""
from .db import consultar_um

CHECAGENS_GRAFO = [
    # (descrição, consulta que devolve um número, regra que o número precisa cumprir, crítica?)
    ("trechos carregados", "SELECT count(*) FROM gold.trechos", lambda n: n >= 10, True),
    ("geometrias inválidas", "SELECT count(*) FROM gold.trechos WHERE NOT ST_IsValid(geom)", lambda n: n == 0, True),
    ("trechos com comprimento zero", "SELECT count(*) FROM gold.trechos WHERE comprimento_m <= 0", lambda n: n == 0, True),
    ("% trechos com inclinação", "SELECT 100.0 * count(inclinacao_pct) / count(*) FROM gold.trechos", lambda n: n >= 50, False),
    ("equipamentos carregados", "SELECT count(*) FROM gold.equipamentos", lambda n: n >= 1, False),
]

CHECAGENS_RELATOS = [
    ("problemas sem geometria", "SELECT count(*) FROM gold.problemas WHERE geom IS NULL", lambda n: n == 0, True),
    ("todo trecho tem custo", "SELECT (SELECT count(*) FROM gold.trechos) - (SELECT count(*) FROM gold.custos_rota)",
     lambda n: n == 0, True),
    ("status válido", """SELECT count(*) FROM gold.problemas
        WHERE status NOT IN ('novo', 'em_verificacao', 'confirmado', 'descartado')""", lambda n: n == 0, True),
]


def checar(checagens):
    falhas = []
    for descricao, sql, regra, critica in checagens:
        valor = float(consultar_um(sql) or 0)
        ok = regra(valor)
        print(f"{'OK    ' if ok else 'FALHOU'} {descricao}: {valor}")
        if critica and not ok:
            falhas.append(descricao)
    if falhas:
        raise ValueError(f"Checagens críticas falharam: {falhas}")