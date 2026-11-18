# Salva o silver em parquet, um formato de arquivo para guardar tabelas. e o bronze em JSON
import json
from datetime import datetime, timezone

import pandas as pd
from  . import config

def _pasta(camada, nome, data):
    pasta = config.LAKE / camada / nome/ f"dt={data}"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta

def salvar_bronze(nome, data, execucao, dados, meta=None):
    pasta = _pasta("bronze", nome, data)/f"{nome}_{execucao}.json"
    envelope = {"fonte": nome, "coletado_em": datetime.now(timezone.utc).isoformat(), "meta": meta or {}, "dados": dados}
    pasta.write_text(json.dumps(envelope, ensure_ascii=False, indent=2))
    return str(pasta)

def ler_bronze(caminho):
   with open(caminho) as f: 
       return json.load(f)["dados"]

def ultimo_bronze(nome, meta=None):
    """Caminho do bronze mais recente dessa fonte (ou None se não houver nenhum).
    Se `meta` for informado, só aceita arquivos salvos com o mesmo meta (ex.: o mesmo BBOX)."""
    arquivos = sorted(
        (config.LAKE / "bronze" / nome).glob(f"dt=*/{nome}_*.json"),
        key=lambda a: (a.parent.name, a.name),  # dt=AAAA-MM-DD e o carimbo da execução ordenam por data
        reverse=True,
    )
    for arquivo in arquivos:
        try:
            with open(arquivo) as f:
                envelope = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue  # arquivo corrompido ou pela metade: ignora
        if meta is None or envelope.get("meta") == meta:
            return str(arquivo)
    return None

def salvar_silver(nome, data, execucao, df):
    caminho = _pasta("silver", nome, data) /f"{nome}_{execucao}.parquet"
    df.to_parquet(caminho, index= False)
    return str(caminho)

def ler_silver(caminho):
    return pd.read_parquet(caminho)
