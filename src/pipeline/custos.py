"""Custo de cada trecho para cada perfil. Custo = comprimento x fatores. -1 = não passe por aqui."""
BLOQUEIA = None

FATORES = {
    #                     padrão  cadeira   idoso  visual
    "escada":            (1.1,   BLOQUEIA,  3,     1.5),
    "inclinacao_5_833":  (1.0,   2,         1.5,   1.0),   # NBR 9050: rampa até 8,33%
    "inclinacao_833_12": (1.0,   5,         2.5,   1.0),
    "inclinacao_12":     (1.2,   BLOQUEIA,  2.5,   1.0),
    "piso_ruim":         (1.1,   3,         1.8,   1.5),
    "sem_calcada":       (1.3,   3,         2,     2.5),
    "guia_alta":         (1.0,   20,        1.5,   1.0),
    "piso_tatil":        (1.0,   1.0,       1.0,   0.85),
    "buraco":            (2,     BLOQUEIA,  4,     6),
    "obstaculo":         (1.5,   BLOQUEIA,  3,     8),
    "falta_rampa":       (1.0,   BLOQUEIA,  1.5,   1.0),
    "alagamento":        (BLOQUEIA, BLOQUEIA, BLOQUEIA, BLOQUEIA),
    "iluminacao_apagada": (1.2,  1.2,       1.5,   1.2),
    "obra":              (2,     BLOQUEIA,  3,     6),
}
PERFIS = ["padrao", "cadeira", "idoso", "visual"]


def situacoes(trecho, problemas):
    """Lista as situações do trecho que mudam o custo."""
    s = []
    if trecho["tem_escada"]:
        s.append("escada")
    i = trecho["inclinacao_pct"]
    if i is not None and i == i:  # i == i é falso quando i é NaN
        if i > 12:
            s.append("inclinacao_12")
        elif i > 8.33:
            s.append("inclinacao_833_12")
        elif i > 5:
            s.append("inclinacao_5_833")
    if trecho["superficie_ruim"] is True:
        s.append("piso_ruim")
    if trecho["calcada"] == "nao":
        s.append("sem_calcada")
    if trecho["travessia"] and trecho["guia_rebaixada"] is False:
        s.append("guia_alta")
    if trecho["piso_tatil"] is True:
        s.append("piso_tatil")
    return s + list(problemas)


def calcular(trecho, problemas):
    """Devolve {'custo_padrao': ..., 'custo_cadeira': ..., ...}."""
    lista = situacoes(trecho, problemas)
    resultado = {}
    for posicao, perfil in enumerate(PERFIS):
        custo = float(trecho["comprimento_m"])
        for situacao in lista:
            fator = FATORES[situacao][posicao]
            if fator is BLOQUEIA:
                custo = -1
                break
            custo *= fator
        resultado[f"custo_{perfil}"] = round(custo, 2)
    return resultado