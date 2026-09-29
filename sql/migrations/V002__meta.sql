-- V002: data-source register, run log and data-quality tables (doc 05 §2.3, §2.5).
-- dw.dim_data_source is created here (not in V003) because meta.load_step and
-- meta.dq_rule reference it.

CREATE TABLE dw.dim_data_source (
    data_source_code VARCHAR(10)   NOT NULL CONSTRAINT pk_dim_data_source PRIMARY KEY,
    name             NVARCHAR(200) NOT NULL,
    licence          NVARCHAR(60)  NOT NULL,
    url              NVARCHAR(400) NULL,
    credit_text      NVARCHAR(400) NOT NULL,
    consent_status   VARCHAR(20)   NOT NULL
        CONSTRAINT ck_dim_data_source_consent CHECK (consent_status IN ('OPEN', 'REQUESTED', 'GRANTED', 'REFUSED')),
    is_publishable   BIT           NOT NULL
);

CREATE TABLE meta.load_run (
    run_id       BIGINT IDENTITY(1, 1) NOT NULL CONSTRAINT pk_load_run PRIMARY KEY,
    started_at   DATETIME2(0) NOT NULL CONSTRAINT df_load_run_started DEFAULT SYSUTCDATETIME(),
    finished_at  DATETIME2(0) NULL,
    status       VARCHAR(10)  NOT NULL
        CONSTRAINT ck_load_run_status CHECK (status IN ('RUNNING', 'SUCCESS', 'WARN', 'FAILED')),
    is_dry_run   BIT          NOT NULL CONSTRAINT df_load_run_dry DEFAULT 0,
    git_commit   CHAR(40)     NULL,
    triggered_by NVARCHAR(128) NOT NULL CONSTRAINT df_load_run_by DEFAULT SUSER_SNAME()
);

CREATE TABLE meta.load_step (
    step_id          BIGINT IDENTITY(1, 1) NOT NULL CONSTRAINT pk_load_step PRIMARY KEY,
    run_id           BIGINT        NOT NULL CONSTRAINT fk_load_step_run REFERENCES meta.load_run (run_id),
    data_source_code VARCHAR(10)   NULL CONSTRAINT fk_load_step_source REFERENCES dw.dim_data_source (data_source_code),
    stage            VARCHAR(12)   NOT NULL
        CONSTRAINT ck_load_step_stage CHECK (stage IN ('EXTRACT', 'LOAD', 'TRANSFORM', 'CHECK', 'FORECAST', 'EXPORT')),
    status           VARCHAR(10)   NOT NULL
        CONSTRAINT ck_load_step_status CHECK (status IN ('RUNNING', 'SUCCESS', 'WARN', 'FAILED', 'SKIPPED')),
    rows_in          INT           NULL,
    rows_merged      INT           NULL,
    source_version   NVARCHAR(100) NULL,
    message          NVARCHAR(MAX) NULL,
    started_at       DATETIME2(0)  NOT NULL CONSTRAINT df_load_step_started DEFAULT SYSUTCDATETIME(),
    finished_at      DATETIME2(0)  NULL
);
CREATE INDEX ix_load_step_run ON meta.load_step (run_id);

CREATE TABLE meta.dq_rule (
    rule_code        VARCHAR(40)   NOT NULL CONSTRAINT pk_dq_rule PRIMARY KEY,
    description      NVARCHAR(400) NOT NULL,
    data_source_code VARCHAR(10)   NULL CONSTRAINT fk_dq_rule_source REFERENCES dw.dim_data_source (data_source_code),
    severity         VARCHAR(8)    NOT NULL CONSTRAINT ck_dq_rule_severity CHECK (severity IN ('BLOCKING', 'WARN')),
    check_sql        NVARCHAR(MAX) NOT NULL,  -- must return the offending rows (zero rows = pass)
    is_active        BIT           NOT NULL CONSTRAINT df_dq_rule_active DEFAULT 1
);

CREATE TABLE meta.dq_result (
    run_id        BIGINT        NOT NULL CONSTRAINT fk_dq_result_run REFERENCES meta.load_run (run_id),
    rule_code     VARCHAR(40)   NOT NULL CONSTRAINT fk_dq_result_rule REFERENCES meta.dq_rule (rule_code),
    status        VARCHAR(4)    NOT NULL CONSTRAINT ck_dq_result_status CHECK (status IN ('PASS', 'WARN', 'FAIL')),
    rows_affected INT           NOT NULL,
    detail        NVARCHAR(MAX) NULL,
    checked_at    DATETIME2(0)  NOT NULL CONSTRAINT df_dq_result_checked DEFAULT SYSUTCDATETIME(),
    CONSTRAINT pk_dq_result PRIMARY KEY (run_id, rule_code)
);
