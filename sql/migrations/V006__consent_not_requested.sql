-- V006: allow 'NOT_REQUESTED' as a consent status. The Energy Commission (D5) needs
-- consent that hasn't been requested yet (doc 01 R3); V002's list had no honest value for it.

ALTER TABLE dw.dim_data_source DROP CONSTRAINT ck_dim_data_source_consent;
ALTER TABLE dw.dim_data_source ADD CONSTRAINT ck_dim_data_source_consent
    CHECK (consent_status IN ('OPEN', 'NOT_REQUESTED', 'REQUESTED', 'GRANTED', 'REFUSED'));
