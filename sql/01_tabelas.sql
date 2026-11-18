
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS app;   -- o que o aplicativo grava (relatos e confirmações)
CREATE SCHEMA IF NOT EXISTS gold;  -- o que o pipeline entrega pronto

-- ---------- app (no MVP, preenchido pela simulação) ----------
CREATE TABLE IF NOT EXISTS app.relatos (
    relato_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_hash text NOT NULL,             -- usuário anônimo, nunca nome ou e-mail (LGPD)
    categoria    text NOT NULL,             -- buraco | obstaculo | falta_rampa | alagamento | iluminacao_apagada | obra
    lat          double precision NOT NULL,
    lon          double precision NOT NULL,
    criado_em    timestamptz NOT NULL DEFAULT now(),
    simulado     boolean NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS app.confirmacoes (
    id           bigserial PRIMARY KEY,
    relato_id    uuid NOT NULL REFERENCES app.relatos(relato_id),
    usuario_hash text NOT NULL,
    resposta     text NOT NULL CHECK (resposta IN ('ainda_esta', 'nao_tem')),
    criado_em    timestamptz NOT NULL DEFAULT now()
);

-- ---------- gold ----------
CREATE TABLE IF NOT EXISTS gold.trechos (
    id             bigint PRIMARY KEY,
    osm_way_id     bigint NOT NULL,
    no_origem      bigint NOT NULL,
    no_destino     bigint NOT NULL,
    nome_via       text,
    tipo_via       text NOT NULL,
    comprimento_m  numeric(9,2) NOT NULL,
    inclinacao_pct numeric(6,2),
    tem_escada     boolean NOT NULL,
    calcada        text NOT NULL,
    superficie_ruim boolean,
    iluminado      boolean,
    travessia      boolean NOT NULL,
    guia_rebaixada boolean,
    piso_tatil     boolean,
    completude     numeric(3,2) NOT NULL,
    geom           geometry(LineString, 4326) NOT NULL,
    atualizado_em  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_trechos_geom ON gold.trechos USING gist (geom);

CREATE TABLE IF NOT EXISTS gold.equipamentos (
    osm_id    bigint PRIMARY KEY,
    categoria text NOT NULL,
    nome      text,
    geom      geometry(Point, 4326) NOT NULL
);

CREATE TABLE IF NOT EXISTS gold.problemas (
    relato_id           uuid PRIMARY KEY,
    categoria           text NOT NULL,
    status              text NOT NULL,      -- novo | em_verificacao | confirmado | descartado
    pessoas_confirmaram integer NOT NULL,
    pessoas_negaram     integer NOT NULL,
    criado_em           timestamptz NOT NULL,
    valido_ate          timestamptz,
    trecho_id           bigint,
    geom                geometry(Point, 4326) NOT NULL,
    atualizado_em       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gold.custos_rota (
    trecho_id        bigint PRIMARY KEY,
    custo_padrao     numeric(12,2) NOT NULL,
    custo_cadeira    numeric(12,2) NOT NULL,   -- -1 = trecho bloqueado
    custo_idoso      numeric(12,2) NOT NULL,
    custo_visual     numeric(12,2) NOT NULL,
    problemas_ativos text[] NOT NULL DEFAULT '{}',
    atualizado_em    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gold.chuva_previsao (
    hora            timestamptz PRIMARY KEY,
    precipitacao_mm numeric(6,2),
    intensidade     text NOT NULL,             -- nenhuma | fraca | moderada | forte
    atualizado_em   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gold.indicadores_diarios (
    dia                      date PRIMARY KEY,
    relatos_recebidos        integer NOT NULL,
    problemas_ativos         integer NOT NULL,
    descartados_total        integer NOT NULL,
    pct_trechos_bem_mapeados numeric(5,1),
    km_liberados_cadeira     numeric(8,2),
    chuva_forte_prevista     boolean NOT NULL,
    atualizado_em            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gold.log_cargas (
    id           bigserial PRIMARY KEY,
    tarefa       text NOT NULL,
    tabela       text NOT NULL,
    linhas       integer NOT NULL,
    carregado_em timestamptz NOT NULL DEFAULT now()
);