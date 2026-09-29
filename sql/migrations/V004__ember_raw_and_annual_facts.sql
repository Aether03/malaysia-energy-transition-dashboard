-- V004: Ember raw landing table and the annual facts (doc 05 §2.1, §2.4).
-- Columns mirror the verified header of release_generation_yearly_global.csv (doc 05 §1.1).

CREATE TABLE raw.ember_yearly (
    area                          NVARCHAR(100)  NOT NULL,
    iso3                          CHAR(3)        NULL,
    year                          SMALLINT       NOT NULL,
    area_type                     NVARCHAR(40)   NOT NULL,
    electricity_source            NVARCHAR(80)   NOT NULL,
    is_aggregated_source          BIT            NOT NULL,
    generation_twh                DECIMAL(12, 4) NULL,
    generation_yoy_twh            DECIMAL(12, 4) NULL,
    generation_yoy_pct            DECIMAL(14, 3) NULL,
    share_of_generation_pct       DECIMAL(7, 3)  NULL,
    share_of_generation_yoy_pp    DECIMAL(7, 3)  NULL,
    capacity_gw                   DECIMAL(10, 4) NULL,
    emissions_mtco2e              DECIMAL(12, 4) NULL,
    emissions_yoy_mtco2e          DECIMAL(12, 4) NULL,
    emissions_yoy_pct             DECIMAL(14, 3) NULL,
    share_of_emissions_pct        DECIMAL(7, 3)  NULL,
    emissions_intensity_gco2e_kwh DECIMAL(10, 3) NULL,
    continent                     NVARCHAR(40)   NULL,
    ember_region                  NVARCHAR(80)   NULL,
    eu_member                     BIT            NULL,
    oecd_member                   BIT            NULL,
    g20_member                    BIT            NULL,
    g7_member                     BIT            NULL,
    asean_member                  BIT            NULL,
    _run_id                       BIGINT         NOT NULL CONSTRAINT fk_ember_yearly_run REFERENCES meta.load_run (run_id),
    _source_file                  NVARCHAR(400)  NOT NULL,
    _loaded_at                    DATETIME2(0)   NOT NULL CONSTRAINT df_ember_yearly_loaded DEFAULT SYSUTCDATETIME(),
    CONSTRAINT pk_ember_yearly PRIMARY KEY (area, year, electricity_source)
);

CREATE TABLE dw.fact_generation_annual (
    country_key      INT            NOT NULL CONSTRAINT fk_fga_country REFERENCES dw.dim_country (country_key),
    year             SMALLINT       NOT NULL CONSTRAINT fk_fga_year REFERENCES dw.dim_year (year),
    source_key       INT            NOT NULL CONSTRAINT fk_fga_source REFERENCES dw.dim_source (source_key),
    generation_twh   DECIMAL(12, 4) NOT NULL,
    share_pct        DECIMAL(7, 3)  NULL,
    capacity_gw      DECIMAL(10, 4) NULL,
    emissions_mtco2e DECIMAL(12, 4) NULL,
    CONSTRAINT pk_fact_generation_annual PRIMARY KEY (country_key, year, source_key)
);

-- One row per country-year. Shares are pre-computed so SQL and DAX can be reconciled
-- (task 2.2). Population and per-capita demand stay NULL until OWID lands (M2).
CREATE TABLE dw.fact_country_annual (
    country_key                   INT            NOT NULL CONSTRAINT fk_fca_country REFERENCES dw.dim_country (country_key),
    year                          SMALLINT       NOT NULL CONSTRAINT fk_fca_year REFERENCES dw.dim_year (year),
    total_generation_twh          DECIMAL(12, 4) NULL,
    demand_twh                    DECIMAL(12, 4) NULL,
    net_imports_twh               DECIMAL(12, 4) NULL,
    emissions_mtco2e              DECIMAL(12, 4) NULL,
    emissions_intensity_gco2e_kwh DECIMAL(10, 3) NULL,
    population                    BIGINT         NULL,
    demand_per_capita_mwh         DECIMAL(10, 4) NULL,
    re_share_gen_pct              DECIMAL(7, 3)  NULL,
    fossil_share_gen_pct          DECIMAL(7, 3)  NULL,
    re_share_capacity_pct         DECIMAL(7, 3)  NULL,
    CONSTRAINT pk_fact_country_annual PRIMARY KEY (country_key, year)
);
