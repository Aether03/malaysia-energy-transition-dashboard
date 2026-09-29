-- V005: least-privilege grants (doc 05 §4). On a single-user PC both roles map to the
-- same Windows login; the grants document the intended separation.

GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::raw  TO role_pipeline;
GRANT SELECT                         ON SCHEMA::stg  TO role_pipeline;
GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::dw   TO role_pipeline;
GRANT SELECT                         ON SCHEMA::ref  TO role_pipeline;
GRANT SELECT, INSERT, UPDATE         ON SCHEMA::meta TO role_pipeline;

GRANT SELECT ON SCHEMA::mart TO role_report_reader;
