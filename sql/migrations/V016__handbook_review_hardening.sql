-- V016: M4 database review (step 8). The parser never lands a missing value: a blank printed
-- cell would be a parse error, and a printed dash is kept as '-'. So value_text is required.
ALTER TABLE raw.handbook_cell ALTER COLUMN value_text NVARCHAR(40) NOT NULL;
