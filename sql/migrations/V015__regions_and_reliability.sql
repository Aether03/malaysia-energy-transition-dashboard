-- V015: M4 regions and state reliability (doc 05 §2.1-2.4; M4 plan Q1, Q3, Q4, Q6).
-- Constraint names follow the V004/V008 convention: pk_/fk_/df_/ck_/uq_<table>_...
-- No new grants: V005 grants are schema-wide, so these tables inherit them.
-- Licence (Q1): raw.handbook_cell holds Energy Commission data. It is filled at runtime from the
-- PDF on this PC only; no row of it is ever exported or committed.

-- Generic landing table for the pinned handbook tables: an exact copy of every cell as printed.
-- Keyed by position, not label (Q3), because labels repeat: p.13's utility rows recur in each
-- region block, and Sarawak's p.85 header prints "2019" twice.
CREATE TABLE raw.handbook_cell (
    edition      SMALLINT      NOT NULL CONSTRAINT ck_handbook_cell_edition CHECK (edition BETWEEN 2000 AND 2100),
    page         SMALLINT      NOT NULL CONSTRAINT ck_handbook_cell_page CHECK (page > 0),
    table_code   VARCHAR(40)   NOT NULL,
    row_pos      SMALLINT      NOT NULL CONSTRAINT ck_handbook_cell_row CHECK (row_pos > 0),  -- 1-based data row, top to bottom
    col_pos      SMALLINT      NOT NULL CONSTRAINT ck_handbook_cell_col CHECK (col_pos > 0),  -- 1-based value column, left to right
    row_group    NVARCHAR(60)  NULL,      -- block the row sits in (p.13 region blocks), from the pinned block order
    row_label    NVARCHAR(150) NOT NULL,  -- as printed; a label wrapped over lines is joined with single spaces
    col_label    NVARCHAR(60)  NOT NULL,  -- as printed
    value_text   NVARCHAR(40)  NULL,      -- as printed (e.g. '1,234.5', '0.8', '-'); cast in stg
    _run_id      BIGINT        NOT NULL CONSTRAINT fk_handbook_cell_run REFERENCES meta.load_run (run_id),
    _source_file NVARCHAR(400) NOT NULL,
    _loaded_at   DATETIME2(0)  NOT NULL CONSTRAINT df_handbook_cell_loaded DEFAULT SYSUTCDATETIME(),
    CONSTRAINT pk_handbook_cell PRIMARY KEY (edition, page, table_code, row_pos, col_pos)
);

CREATE TABLE dw.dim_region (
    region_key    INT IDENTITY(1, 1) NOT NULL CONSTRAINT pk_dim_region PRIMARY KEY,
    region_code   CHAR(3)      NOT NULL CONSTRAINT uq_dim_region_code UNIQUE
                               CONSTRAINT ck_dim_region_code CHECK (region_code IN ('PEN', 'SAB', 'SAR')),
    name          NVARCHAR(40) NOT NULL CONSTRAINT uq_dim_region_name UNIQUE,
    display_order SMALLINT     NOT NULL CONSTRAINT uq_dim_region_order UNIQUE
);

-- The 16 geoBoundaries MYS ADM1 units (13 states + 3 federal territories). iso_3166_2 is the
-- Shape Map join key (M4 step 1: shapeISO joins as well as shapeName and doesn't depend on
-- spelling); geo_shape_name keeps the exact shapeName (e.g. 'Malacca', 'Penang').
-- Labuan belongs to SAB: the handbook's Sabah figures include WP Labuan (p.18 note).
CREATE TABLE dw.dim_state (
    state_key            INT IDENTITY(1, 1) NOT NULL CONSTRAINT pk_dim_state PRIMARY KEY,
    state_code           CHAR(3)      NOT NULL CONSTRAINT uq_dim_state_code UNIQUE,
    name                 NVARCHAR(60) NOT NULL CONSTRAINT uq_dim_state_name UNIQUE,
    geo_shape_name       NVARCHAR(60) NOT NULL CONSTRAINT uq_dim_state_shape UNIQUE,
    iso_3166_2           CHAR(5)      NOT NULL CONSTRAINT uq_dim_state_iso UNIQUE
                                      CONSTRAINT ck_dim_state_iso CHECK (iso_3166_2 LIKE 'MY-[0-9][0-9]'),
    region_key           INT          NOT NULL CONSTRAINT fk_dim_state_region REFERENCES dw.dim_region (region_key),
    is_federal_territory BIT          NOT NULL,
    display_order        SMALLINT     NOT NULL CONSTRAINT uq_dim_state_order UNIQUE
);

-- Every spelling the handbook (or the boundary file) uses for a state, mapped to its code.
-- A label missing here fails the STATE_ALIAS_COMPLETE BLOCKING rule rather than being dropped.
CREATE TABLE ref.state_alias (
    alias      NVARCHAR(100) NOT NULL CONSTRAINT pk_state_alias PRIMARY KEY,
    state_code CHAR(3)       NOT NULL CONSTRAINT fk_state_alias_state REFERENCES dw.dim_state (state_code)
);

-- Regional indicators in long form (metrics vary by handbook table). A missing row = not
-- reported; a printed '-' lands as NULL. Totals are the printed totals, never re-summed here.
CREATE TABLE dw.fact_region_annual (
    region_key  INT            NOT NULL CONSTRAINT fk_fra_region REFERENCES dw.dim_region (region_key),
    year        SMALLINT       NOT NULL CONSTRAINT fk_fra_year REFERENCES dw.dim_year (year),
    metric_code VARCHAR(30)    NOT NULL CONSTRAINT ck_fra_metric CHECK (metric_code IN (
                    'INSTALLED_MW', 'AVAILABLE_MW', 'ELEC_CONSUMPTION_GWH', 'ELEC_PER_CAPITA_KWH',
                    'POPULATION_K', 'SUPPLY_INTERRUPTIONS', 'SAIFI', 'SAIDI_MIN')),
    value       DECIMAL(14, 3) NULL CONSTRAINT ck_fra_value CHECK (value IS NULL OR value >= 0),
    unit        NVARCHAR(30)   NOT NULL,
    page        SMALLINT       NOT NULL,  -- handbook page the value came from (lineage)
    CONSTRAINT pk_fact_region_annual PRIMARY KEY (region_key, year, metric_code)
);

-- Installed and available capacity by region and doc 04 fuel group (p.13/p.14, as of 31 Dec of
-- `year`). Separate from fact_region_annual because the fuel breakdown is part of the key.
CREATE TABLE dw.fact_region_capacity (
    region_key   INT            NOT NULL CONSTRAINT fk_frc_region REFERENCES dw.dim_region (region_key),
    year         SMALLINT       NOT NULL CONSTRAINT fk_frc_year REFERENCES dw.dim_year (year),
    source_key   INT            NOT NULL CONSTRAINT fk_frc_source REFERENCES dw.dim_source (source_key),
    installed_mw DECIMAL(10, 1) NULL CONSTRAINT ck_frc_installed CHECK (installed_mw IS NULL OR installed_mw >= 0),
    available_mw DECIMAL(10, 1) NULL CONSTRAINT ck_frc_available CHECK (available_mw IS NULL OR available_mw >= 0),
    CONSTRAINT pk_fact_region_capacity PRIMARY KEY (region_key, year, source_key),
    CONSTRAINT ck_frc_some_value CHECK (installed_mw IS NOT NULL OR available_mw IS NOT NULL)
);

-- SAIFI and SAIDI by Peninsular state, as printed (p.84, p.83). NULL = not reported.
CREATE TABLE dw.fact_state_reliability (
    state_key INT           NOT NULL CONSTRAINT fk_fsr_state REFERENCES dw.dim_state (state_key),
    year      SMALLINT      NOT NULL CONSTRAINT fk_fsr_year REFERENCES dw.dim_year (year),
    saifi     DECIMAL(6, 3) NULL CONSTRAINT ck_fsr_saifi CHECK (saifi IS NULL OR saifi >= 0),
    saidi_min DECIMAL(8, 2) NULL CONSTRAINT ck_fsr_saidi CHECK (saidi_min IS NULL OR saidi_min >= 0),
    CONSTRAINT pk_fact_state_reliability PRIMARY KEY (state_key, year)
);
