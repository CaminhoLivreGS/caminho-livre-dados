"""Carga da camada gold (camada que o app, o painel e o robo irão ler)no PostgreSQL."""
import psycopg2.extras

from . import custos
from .db import conectar, inserir_varios


def _vazio_para_none(v):
    """O pandas usa NaN para 'sem valor'; o banco precisa de None (NULL)."""
    return None if v is None or v != v else (v.item() if hasattr(v, "item") else v)


def registrar(cur, tarefa, tabela, linhas):
    cur.execute("INSERT INTO gold.log_cargas (tarefa, tabela, linhas) VALUES (%s, %s, %s)", (tarefa, tabela, linhas))


def carregar_trechos(df_trechos, df_equip):
    """Troca o grafo inteiro numa única transação: o app nunca vê o grafo pela metade."""
    colunas = ["id", "osm_way_id", "no_origem", "no_destino", "nome_via", "tipo_via", "comprimento_m",
               "inclinacao_pct", "tem_escada", "calcada", "superficie_ruim", "iluminado", "travessia",
               "guia_rebaixada", "piso_tatil", "completude"]
    linhas = [tuple(_vazio_para_none(linha[c]) for c in colunas) + ("SRID=4326;" + linha["geom_wkt"],)
              for _, linha in df_trechos.iterrows()]
    with conectar() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE gold.trechos, gold.custos_rota, gold.equipamentos")
        inserir_varios(cur, f"INSERT INTO gold.trechos ({', '.join(colunas)}, geom) VALUES %s", linhas)
        inserir_varios(cur, "INSERT INTO gold.equipamentos (osm_id, categoria, nome, geom) VALUES %s",
                       [(int(r.osm_id), r.categoria, _vazio_para_none(r.nome), f"SRID=4326;POINT({r.lon} {r.lat})")
                        for r in df_equip.itertuples()])
        registrar(cur, "carregar_trechos", "gold.trechos", len(linhas))
        registrar(cur, "carregar_trechos", "gold.equipamentos", len(df_equip))
    return len(linhas)


def carregar_problemas(df):
    colunas = ["relato_id", "categoria", "status", "pessoas_confirmaram", "pessoas_negaram", "criado_em", "valido_ate"]
    linhas = [tuple(_vazio_para_none(getattr(r, c)) for c in colunas) + (f"SRID=4326;POINT({r.lon} {r.lat})",)
              for r in df.itertuples()]
    with conectar() as conn, conn.cursor() as cur:
        inserir_varios(cur, f"""
            INSERT INTO gold.problemas ({', '.join(colunas)}, geom) VALUES %s
            ON CONFLICT (relato_id) DO UPDATE SET status = EXCLUDED.status,
              pessoas_confirmaram = EXCLUDED.pessoas_confirmaram, pessoas_negaram = EXCLUDED.pessoas_negaram,
              valido_ate = EXCLUDED.valido_ate, atualizado_em = now()""", linhas)
        # Liga cada problema ao trecho mais próximo, se estiver a até 30 metros
        cur.execute("""
            UPDATE gold.problemas p SET trecho_id = (
                SELECT t.id FROM gold.trechos t
                WHERE ST_DWithin(t.geom::geography, p.geom::geography, 30)
                ORDER BY t.geom <-> p.geom LIMIT 1)""")
        registrar(cur, "carregar_problemas", "gold.problemas", len(linhas))
    return len(linhas)


def recalcular_custos():
    """Para cada trecho, junta os problemas confirmados e calcula o custo de cada perfil."""
    with conectar() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT t.*, coalesce(array_agg(p.categoria) FILTER (WHERE p.status = 'confirmado'), '{}') AS ativos
            FROM gold.trechos t LEFT JOIN gold.problemas p ON p.trecho_id = t.id
            GROUP BY t.id""")
        trechos = cur.fetchall()
    linhas = []
    for t in trechos:
        c = custos.calcular(t, t["ativos"])
        linhas.append((t["id"], c["custo_padrao"], c["custo_cadeira"], c["custo_idoso"], c["custo_visual"], t["ativos"]))
    with conectar() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE gold.custos_rota")
        inserir_varios(cur, """INSERT INTO gold.custos_rota
            (trecho_id, custo_padrao, custo_cadeira, custo_idoso, custo_visual, problemas_ativos) VALUES %s""", linhas)
        registrar(cur, "recalcular_custos", "gold.custos_rota", len(linhas))
    return len(linhas)


def carregar_chuva(df):
    with conectar() as conn, conn.cursor() as cur:
        inserir_varios(cur, """
            INSERT INTO gold.chuva_previsao (hora, precipitacao_mm, intensidade) VALUES %s
            ON CONFLICT (hora) DO UPDATE SET precipitacao_mm = EXCLUDED.precipitacao_mm,
              intensidade = EXCLUDED.intensidade, atualizado_em = now()""",
            [(r.hora.to_pydatetime(), _vazio_para_none(r.precipitacao_mm), r.intensidade) for r in df.itertuples()])
        registrar(cur, "carregar_chuva", "gold.chuva_previsao", len(df))
    return len(df)


def calcular_indicadores():
    with conectar() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO gold.indicadores_diarios AS i (dia, relatos_recebidos, problemas_ativos, descartados_total,
                pct_trechos_bem_mapeados, km_liberados_cadeira, chuva_forte_prevista)
            SELECT current_date,
              (SELECT count(*) FROM app.relatos WHERE criado_em::date = current_date),
              (SELECT count(*) FROM gold.problemas WHERE status = 'confirmado'),
              (SELECT count(*) FROM gold.problemas WHERE status = 'descartado'),
              (SELECT round(100.0 * count(*) FILTER (WHERE completude >= 0.75) / count(*), 1) FROM gold.trechos),
              (SELECT round(sum(t.comprimento_m) / 1000, 2) FROM gold.trechos t
                 JOIN gold.custos_rota c ON c.trecho_id = t.id WHERE c.custo_cadeira >= 0),
              EXISTS (SELECT 1 FROM gold.chuva_previsao
                      WHERE hora BETWEEN now() AND now() + interval '6 hours' AND intensidade = 'forte')
            ON CONFLICT (dia) DO UPDATE SET relatos_recebidos = EXCLUDED.relatos_recebidos,
              problemas_ativos = EXCLUDED.problemas_ativos, descartados_total = EXCLUDED.descartados_total,
              pct_trechos_bem_mapeados = EXCLUDED.pct_trechos_bem_mapeados,
              km_liberados_cadeira = EXCLUDED.km_liberados_cadeira,
              chuva_forte_prevista = EXCLUDED.chuva_forte_prevista, atualizado_em = now()
            RETURNING row_to_json(i)""")
        resultado = cur.fetchone()[0]
        registrar(cur, "calcular_indicadores", "gold.indicadores_diarios", 1)
    print(resultado)
    return resultado