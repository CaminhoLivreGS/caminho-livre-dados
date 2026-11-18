"""DAG 1 — Base do território (toda semana).
OpenStreetMap + altitude → trechos de calçada com acessibilidade → gold.trechos
"""
from datetime import datetime, timedelta

from airflow.decorators import dag, task


@dag(
    dag_id="cl_base_territorio",
    schedule="@weekly",
    start_date=datetime(2026, 11, 1),
    catchup=False,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=2)},
    tags=["caminho-livre"],
)
def base_territorio():

    @task
    def criar_tabelas():
        from pipeline import db
        db.rodar_sql_arquivo("01_tabelas.sql")

    # A Overpass pública vive sobrecarregada: tenta mais vezes e espera cada vez mais (10, 20, 40 min...)
    @task(retries=4, retry_delay=timedelta(minutes=10), retry_exponential_backoff=True,
          max_retry_delay=timedelta(hours=1))
    def extrair_osm(ds=None, ts_nodash=None, ti=None):
        from pipeline import config, lake, osm
        meta = {"bbox": list(config.BBOX)}  # só reaproveita bronze do mesmo retângulo
        try:
            return lake.salvar_bronze("osm", ds, ts_nodash, osm.baixar(), meta=meta)
        except RuntimeError:
            ultima_tentativa = ti.try_number > ti.max_tries
            anterior = lake.ultimo_bronze("osm", meta=meta)
            if not ultima_tentativa or anterior is None:
                raise  # ainda há tentativas (ou não há plano B): deixa o Airflow tentar de novo
            # Plano B: ruas e calçadas mudam pouco de uma semana para outra
            print(f"AVISO: Overpass indisponível. Reaproveitando o último OSM salvo: {anterior}")
            return anterior

    @task
    def transformar_trechos(caminho_osm, ds=None, ts_nodash=None):
        from pipeline import grafo, lake
        nos, trechos, equip = grafo.construir(lake.ler_bronze(caminho_osm))
        print(f"{len(trechos)} trechos, {len(nos)} nós, {len(equip)} equipamentos")
        return {
            "nos": lake.salvar_silver("nos", ds, ts_nodash, nos),
            "trechos": lake.salvar_silver("trechos", ds, ts_nodash, trechos),
            "equipamentos": lake.salvar_silver("equipamentos", ds, ts_nodash, equip),
        }

    @task
    def extrair_altitude(silver, ds=None, ts_nodash=None):
        from pipeline import grafo, lake
        altitudes = grafo.buscar_altitude(lake.ler_silver(silver["nos"]))
        return lake.salvar_bronze("altitude", ds, ts_nodash, altitudes)

    @task
    def calcular_inclinacao(silver, caminho_altitude, ds=None, ts_nodash=None):
        from pipeline import grafo, lake
        trechos = grafo.calcular_inclinacao(lake.ler_silver(silver["trechos"]), lake.ler_bronze(caminho_altitude))
        trechos["completude"] = grafo.calcular_completude(trechos)
        return {**silver, "trechos": lake.salvar_silver("trechos_final", ds, ts_nodash, trechos)}

    @task
    def carregar_gold(silver):
        from pipeline import carga, lake
        return carga.carregar_trechos(lake.ler_silver(silver["trechos"]), lake.ler_silver(silver["equipamentos"]))

    @task
    def checar_qualidade():
        from pipeline import qualidade
        qualidade.checar(qualidade.CHECAGENS_GRAFO)

    @task
    def calcular_custos():
        from pipeline import carga
        return carga.recalcular_custos()

    # A ordem das tarefas
    tabelas = criar_tabelas()
    osm = extrair_osm()
    tabelas >> osm
    silver = transformar_trechos(osm)
    altitude = extrair_altitude(silver)
    final = calcular_inclinacao(silver, altitude)
    carregar_gold(final) >> checar_qualidade() >> calcular_custos()


base_territorio()