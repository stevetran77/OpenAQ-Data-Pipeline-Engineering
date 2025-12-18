-- ============================================================================
-- OpenAQ Data Warehouse Schema
-- ============================================================================

-- Create schema
CREATE SCHEMA IF NOT EXISTS openaq;

-- ============================================================================
-- Fact Table: Air Quality Measurements
-- ============================================================================
CREATE TABLE IF NOT EXISTS openaq.fact_measurements (
    measurement_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    location_id INTEGER NOT NULL,
    measurement_datetime TIMESTAMP NOT NULL,
    pm25 DECIMAL(10,4),
    pm10 DECIMAL(10,4),
    o3 DECIMAL(10,4),
    no2 DECIMAL(10,4),
    so2 DECIMAL(10,4),
    co DECIMAL(10,4),
    latitude DECIMAL(10,6),
    longitude DECIMAL(10,6),
    city VARCHAR(100),
    country VARCHAR(10),
    extracted_at TIMESTAMP,
    loaded_at TIMESTAMP DEFAULT GETDATE(),
    UNIQUE(location_id, measurement_datetime)
)
DISTSTYLE KEY
DISTKEY(city)
SORTKEY(measurement_datetime);

-- ============================================================================
-- Dimension Table: Locations
-- ============================================================================
CREATE TABLE IF NOT EXISTS openaq.dim_locations (
    location_id INTEGER PRIMARY KEY,
    location_name VARCHAR(255),
    city VARCHAR(100),
    country VARCHAR(10),
    latitude DECIMAL(10,6),
    longitude DECIMAL(10,6),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT GETDATE(),
    updated_at TIMESTAMP DEFAULT GETDATE()
)
DISTSTYLE ALL;

-- ============================================================================
-- Indexes for Query Performance
-- ============================================================================
-- Note: Redshift uses sort keys instead of traditional indexes
-- The SORTKEY on measurement_datetime optimizes time-range queries

-- ============================================================================
-- Service Account for Looker (Read-Only)
-- ============================================================================
-- CREATE USER looker_readonly PASSWORD 'secure_password';
-- GRANT USAGE ON SCHEMA openaq TO looker_readonly;
-- GRANT SELECT ON ALL TABLES IN SCHEMA openaq TO looker_readonly;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA openaq GRANT SELECT ON TABLES TO looker_readonly;
