-- V011: keep raw.grid_interval an exact copy (M3 plan Q1) for Singapore (EMA, M3 Q4 outcome).
-- EMA's System Demand values are computed and carry up to 15 decimals (e.g. 5760.359344156905);
-- DECIMAL(12,2) would round them on landing. Six decimals keep every EGAT value exactly and EMA
-- values to 1 microwatt-scale unit, far below the source's own accuracy. Widening is lossless.
ALTER TABLE raw.grid_interval ALTER COLUMN value DECIMAL(18, 6) NULL;
