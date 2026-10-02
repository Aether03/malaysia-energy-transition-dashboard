-- V012: Singapore public holidays (M3 Q4 outcome): the SG grid's day-type split and forecast
-- features need them, as TH and MY have theirs.
ALTER TABLE ref.public_holiday DROP CONSTRAINT ck_public_holiday_country;
ALTER TABLE ref.public_holiday ADD CONSTRAINT ck_public_holiday_country CHECK (country_code IN ('TH', 'MY', 'SG'));
ALTER TABLE dw.dim_date ADD is_holiday_sg BIT NOT NULL CONSTRAINT df_dim_date_holiday_sg DEFAULT 0;
