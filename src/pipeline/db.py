#Conexão com PostgreSQL
import psycopg2
import psycopg2.extras

from . import config

#conecta ao banco de dados, retorna um objeto de conexão.
def conectar():
    return psycopg2.connect(config.DB_DSN)


#Executa um arquivo SQL que está na pasta sql do projeto.
def rodar_sql_arquivo(nome): 
    sql = (config.SQL / nome ).read_text()
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(sql)


def inserir_varios(cur, sql, linhas):
    if linhas:
        psycopg2.extras.execute_values(cur, sql, linhas, page_size=1000)

def consultar_um(sql):
    with conectar() as conn, conn.cursor() as cur: # Faz commit automático se tudo der certo, se der errado faz rollback    
        cur.execute(sql)
        return cur.fetchone()[0]

