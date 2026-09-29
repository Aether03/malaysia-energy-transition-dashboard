-- V003: annual dimensions and hand-authored reference tables (doc 05 §2.2-2.3).

CREATE TABLE dw.dim_source (
    source_key     INT IDENTITY(1, 1) NOT NULL CONSTRAINT pk_dim_source PRIMARY KEY,
    source_code    VARCHAR(20)  NOT NULL CONSTRAINT uq_dim_source_code UNIQUE,
    display_name   NVARCHAR(40) NOT NULL,
    group_name     VARCHAR(10)  NOT NULL CONSTRAINT ck_dim_source_group CHECK (group_name IN ('FOSSIL', 'RENEWABLE')),
    sort_order     SMALLINT     NOT NULL CONSTRAINT uq_dim_source_sort UNIQUE,  -- stacking order, doc 04 §3.2
    color_hex      CHAR(7)      NOT NULL CONSTRAINT ck_dim_source_color CHECK (color_hex LIKE '#[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'),
    color_hex_dark CHAR(7)      NOT NULL CONSTRAINT ck_dim_source_color_dark CHECK (color_hex_dark LIKE '#[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]')
);

-- ember_area is Ember's own label: the join key for rows without an ISO3 code
-- (the "ASEAN" aggregate). Countries join on iso3.
CREATE TABLE dw.dim_country (
    country_key     INT IDENTITY(1, 1) NOT NULL CONSTRAINT pk_dim_country PRIMARY KEY,
    iso3            CHAR(3)       NULL,
    ember_area      NVARCHAR(100) NOT NULL CONSTRAINT uq_dim_country_area UNIQUE,
    name            NVARCHAR(100) NOT NULL CONSTRAINT uq_dim_country_name UNIQUE,
    area_type       VARCHAR(10)   NOT NULL CONSTRAINT ck_dim_country_type CHECK (area_type IN ('COUNTRY', 'REGION')),
    is_asean        BIT           NOT NULL,
    is_focus        BIT           NOT NULL CONSTRAINT df_dim_country_focus DEFAULT 0,
    is_default_peer BIT           NOT NULL CONSTRAINT df_dim_country_peer DEFAULT 0,
    display_order   SMALLINT      NOT NULL
);
CREATE UNIQUE INDEX uq_dim_country_iso3 ON dw.dim_country (iso3) WHERE iso3 IS NOT NULL;
CREATE UNIQUE INDEX uq_dim_country_focus ON dw.dim_country (is_focus) WHERE is_focus = 1;  -- one focus country

CREATE TABLE dw.dim_year (
    year        SMALLINT NOT NULL CONSTRAINT pk_dim_year PRIMARY KEY,
    is_complete BIT      NOT NULL,
    decade      SMALLINT NOT NULL
);

CREATE TABLE ref.source_map (
    ember_source   NVARCHAR(80) NOT NULL CONSTRAINT pk_source_map PRIMARY KEY,
    source_code    VARCHAR(20)  NULL CONSTRAINT fk_source_map_source REFERENCES dw.dim_source (source_code),
    include_in_mix BIT          NOT NULL,
    CONSTRAINT ck_source_map_mix CHECK (include_in_mix = 0 OR source_code IS NOT NULL)
);

CREATE TABLE ref.netr_target (
    target_year           SMALLINT      NOT NULL CONSTRAINT pk_netr_target PRIMARY KEY,
    re_capacity_share_pct DECIMAL(5, 2) NOT NULL CONSTRAINT ck_netr_target_pct CHECK (re_capacity_share_pct BETWEEN 0 AND 100),
    source_url            NVARCHAR(400) NOT NULL
);

CREATE TABLE ref.kpi (
    kpi_code         VARCHAR(30)   NOT NULL CONSTRAINT pk_kpi PRIMARY KEY,
    name             NVARCHAR(80)  NOT NULL,
    definition       NVARCHAR(400) NOT NULL,
    formula          NVARCHAR(400) NOT NULL,
    unit             NVARCHAR(20)  NOT NULL,
    polarity         SMALLINT      NOT NULL CONSTRAINT ck_kpi_polarity CHECK (polarity IN (-1, 1)),  -- +1 up = good
    data_source_code VARCHAR(10)   NOT NULL CONSTRAINT fk_kpi_source REFERENCES dw.dim_data_source (data_source_code)
);
