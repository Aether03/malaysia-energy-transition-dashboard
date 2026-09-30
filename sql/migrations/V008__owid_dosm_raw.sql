-- V008: M2 sources and reference data (doc 05 §2.1; M2 plan steps 1-3).
-- Constraint names follow the V004 convention: pk_<table>, fk_<table>_run, df_<table>_<col>,
-- ck_<table>_<rule> (M2 plan Q6b; existing objects are not renamed).

-- D2: OWID energy dataset, ASEAN members only; keeps OWID's own column names.
CREATE TABLE raw.owid_energy (
    country                     NVARCHAR(100)  NOT NULL,
    year                        SMALLINT       NOT NULL,
    iso_code                    CHAR(3)        NOT NULL,
    population                  BIGINT         NULL,
    per_capita_electricity      DECIMAL(14, 4) NULL,  -- kWh per person (OWID's generation basis)
    electricity_demand          DECIMAL(14, 4) NULL,  -- TWh
    electricity_generation      DECIMAL(14, 4) NULL,  -- TWh
    carbon_intensity_elec       DECIMAL(14, 4) NULL,  -- gCO2e/kWh
    renewables_share_elec       DECIMAL(14, 4) NULL,  -- %
    coal_electricity            DECIMAL(14, 4) NULL,  -- TWh (this and the rest)
    gas_electricity             DECIMAL(14, 4) NULL,
    oil_electricity             DECIMAL(14, 4) NULL,
    hydro_electricity           DECIMAL(14, 4) NULL,
    solar_electricity           DECIMAL(14, 4) NULL,
    wind_electricity            DECIMAL(14, 4) NULL,
    biofuel_electricity         DECIMAL(14, 4) NULL,
    other_renewable_electricity DECIMAL(14, 4) NULL,
    greenhouse_gas_emissions    DECIMAL(14, 4) NULL,  -- MtCO2e
    _run_id                     BIGINT         NOT NULL CONSTRAINT fk_owid_energy_run REFERENCES meta.load_run (run_id),
    _source_file                NVARCHAR(400)  NOT NULL,
    _loaded_at                  DATETIME2(0)   NOT NULL CONSTRAINT df_owid_energy_loaded DEFAULT SYSUTCDATETIME(),
    CONSTRAINT pk_owid_energy PRIMARY KEY (iso_code, year)
);

-- D3: DOSM monthly electricity supply and consumption (GWh); series ends Jun 2024 (S1).
CREATE TABLE raw.dosm_electricity (
    month        DATE           NOT NULL,
    sector       NVARCHAR(40)   NOT NULL,
    measure      NVARCHAR(20)   NOT NULL CONSTRAINT ck_dosm_electricity_measure CHECK (measure IN (N'supply', N'consumption')),
    value_gwh    DECIMAL(14, 4) NOT NULL,
    _run_id      BIGINT         NOT NULL CONSTRAINT fk_dosm_electricity_run REFERENCES meta.load_run (run_id),
    _source_file NVARCHAR(400)  NOT NULL,
    _loaded_at   DATETIME2(0)   NOT NULL CONSTRAINT df_dosm_electricity_loaded DEFAULT SYSUTCDATETIME(),
    CONSTRAINT pk_dosm_electricity PRIMARY KEY (month, sector, measure)
);

-- Capacity factor needs the hours in each year (8,784 in leap years; doc 03 P2).
ALTER TABLE dw.dim_year ADD hours_in_year AS
    CAST(CASE WHEN (year % 4 = 0 AND year % 100 <> 0) OR year % 400 = 0 THEN 8784 ELSE 8760 END AS SMALLINT) PERSISTED;

-- Step 1 decision: each target cites its own source document.
ALTER TABLE ref.netr_target ADD source_name NVARCHAR(200) NULL;

-- Step 1 decision: official reported progress, shown beside the Ember-basis series.
CREATE TABLE ref.re_capacity_official (
    year                  SMALLINT      NOT NULL CONSTRAINT pk_re_capacity_official PRIMARY KEY,
    re_capacity_share_pct DECIMAL(5, 2) NOT NULL CONSTRAINT ck_re_capacity_official_pct CHECK (re_capacity_share_pct BETWEEN 0 AND 100),
    basis                 NVARCHAR(200) NOT NULL,
    source_name           NVARCHAR(200) NOT NULL,
    source_url            NVARCHAR(400) NOT NULL,
    as_of                 DATE          NOT NULL
);
