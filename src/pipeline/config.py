#Central de configurações do projeto, ele não realiza nenhuma ação, apenas guarda as variáveis de ambiente e constantes do projeto.
import os # permite ler as variaveis de ambiente  
from pathlib import Path 

#retangulo do bairro que a pipeline vai buscar no mapa
BBOX = tuple(float(x) for x in os.getenv("CL_BBOX", "-23.5375,-46.7975,-23.5275,-46.7865").split(","))

#Endereço do banco de dados onde fica a camada gold 
DB_DSN = os.getenv("CL_DB_DSN", "postgresql://caminho:caminho@localhost:5432/caminho_livre")


RAIZ = Path(os.getenv("CL_RAIZ", "/opt/airflow")) #Pasta principal do projeto
LAKE = RAIZ / "data" / "lake" # Onde fica o bronze e o silver 
SQL = RAIZ / "sql"

# os.getenv significa procure essa variavel, se não encontrar use o valor padrão. 

# Lista de servidores Overpass, separados por vírgula. Se um falhar, a pipeline tenta o próximo.
OVERPASS_URLS = [u.strip() for u in os.getenv(
    "CL_OVERPASS_URLS",
    "https://overpass-api.de/api/interpreter,"
    "https://overpass.private.coffee/api/interpreter,"
    "https://overpass.kumi.systems/api/interpreter,"
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
).split(",") if u.strip()]
# Os servidores públicos exigem identificação; sem isso respondem 429 ou bloqueiam.
USER_AGENT = os.getenv("CL_USER_AGENT", "caminho-livre-dados/1.0 (pipeline de acessibilidade urbana)")
ELEVACAO_URL = os.getenv("CL_ELEVACAO_URL", "https://api.opentopodata.org/v1/srtm30m")
CHUVA_URL = os.getenv("CL_CHUVA_URL", "https://api.open-meteo.com/v1/forecast")