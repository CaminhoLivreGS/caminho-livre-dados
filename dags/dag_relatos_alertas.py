
from datetime import datetime, timedelta

from airflow.decorators import dag, task


@dag(
    dag_id="cl_relatos_alertas",
    schedule="*/15 * * * *",
    start_date=datetime(2026, 11, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=1)},
    tags=["caminho-livre"],
)
def relatos_alertas():

    @task
    def simular_uso_do_app(ts_nodash=None):
        from pipeline import simulacao
        return simulacao.simular(semente=ts_nodash)

    @task
    def extrair_relatos(ds=None, ts_nodash=None):
        from pipeline import lake, relatos
        r, resp = relatos.extrair()
        return {"relatos": lake.salvar_silver("relatos_brutos", ds, ts_nodash, r),
                "respostas": lake.salvar_silver("respostas_brutas", ds, ts_nodash, resp)}

    @task
    def consolidar_status(caminhos, ds=None, ts_nodash=None):
        import pandas as pd
        from pipeline import config, lake, relatos
        r = relatos.limpar(lake.ler_silver(caminhos["relatos"]), config.BBOX)
        problemas = relatos.consolidar(r, lake.ler_silver(caminhos["respostas"]), pd.Timestamp.now(tz="UTC"))
        return lake.salvar_silver("problemas", ds, ts_nodash, problemas)

    @task
    def carregar_problemas(caminho):
        from pipeline import carga, lake
        return carga.carregar_problemas(lake.ler_silver(caminho))

    @task
    def extrair_chuva(ds=None, ts_nodash=None):
        from pipeline import chuva, lake
        return lake.salvar_bronze("chuva", ds, ts_nodash, chuva.baixar())

    @task
    def carregar_chuva(caminho):
        from pipeline import carga, chuva, lake
        return carga.carregar_chuva(chuva.transformar(lake.ler_bronze(caminho)))

    @task
    def recalcular_custos():
        from pipeline import carga
        return carga.recalcular_custos()

    @task
    def checar_qualidade():
        from pipeline import qualidade
        qualidade.checar(qualidade.CHECAGENS_RELATOS)

    @task
    def calcular_indicadores():
        from pipeline import carga
        return carga.calcular_indicadores()

    relatos = extrair_relatos()
    simular_uso_do_app() >> relatos          # primeiro simula, depois lê o banco
    problemas = carregar_problemas(consolidar_status(relatos))
    chuva = carregar_chuva(extrair_chuva())
    [problemas, chuva] >> recalcular_custos() >> checar_qualidade() >> calcular_indicadores()


relatos_alertas()