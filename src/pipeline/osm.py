# Extrai os dados da API openstreetmap, tudo o que o pedestre pode usar, como calçadas, faixas de pedestres, rampas, escolas, hospitais, etc.
import time

import requests

from . import config

# Consulta na api, em sua linguagem propria. 
CONSULTA = """
[out:json][timeout:120]; 
(
  way["highway"~"^(footway|pedestrian|path|steps|living_street|residential|tertiary|secondary|primary|unclassified|service)$"]({s},{w},{n},{e});
  node["highway"~"^(crossing|traffic_signals|bus_stop)$"]({s},{w},{n},{e});
  node["kerb"]({s},{w},{n},{e});
  node["amenity"~"^(clinic|doctors|hospital|school|pharmacy)$"]({s},{w},{n},{e});
  node["railway"="station"]({s},{w},{n},{e});
);
out body;
>;
out skel qt;
"""


def baixar(rodadas=3):
    s, w, n, e = config.BBOX # A consulta será feita dentro desse rentagulo definido pelo usuario
    consulta = CONSULTA.format(s=s, w=w, n=n, e=e)
    cabecalho = {"User-Agent": config.USER_AGENT}
    erros = []
    # Em cada rodada passa por todos os servidores; se um estiver fora do ar, tenta o próximo.
    for rodada in range(1, rodadas + 1):
        for url in config.OVERPASS_URLS:
            try:
                # (15, 180): até 15s para conectar e até 180s esperando a resposta
                resp = requests.post(url, data={"data": consulta}, headers=cabecalho, timeout=(15, 180))
                resp.raise_for_status()
                dados = resp.json()
                if "elements" not in dados:
                    raise ValueError(f"resposta sem 'elements': {str(dados)[:200]}")
                if dados.get("remark"):  # a Overpass avisa aqui quando a consulta estourou tempo/memória
                    raise ValueError(f"consulta incompleta: {dados['remark']}")
                print(f"OSM: {len(dados['elements'])} elementos recebidos de {url}")
                return dados
            except (requests.RequestException, ValueError) as erro:
                print(f"Rodada {rodada}, {url} falhou: {erro}")
                erros.append(f"{url}: {erro}")
        if rodada < rodadas:
            time.sleep(30 * rodada)  # servidores sobrecarregados (429/504) precisam de uma pausa maior
    raise RuntimeError(f"Nenhum servidor Overpass respondeu depois de {rodadas} rodadas. Último erro: {erros[-1]}")
