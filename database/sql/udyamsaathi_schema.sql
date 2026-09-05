CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- for fuzzy name matching later
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- provides gen_random_uuid()

-- ============================================================================
-- 1.1 REFERENCE / IDENTITY LAYER
-- ============================================================================

CREATE TABLE states (
    state_code          VARCHAR(2)  PRIMARY KEY,      -- LGD state code, e.g. '27' = Maharashtra
    census_2011_code    VARCHAR(2),
    state_name          TEXT NOT NULL,
    state_name_normalized TEXT NOT NULL,               -- lowercase, trimmed, for fuzzy join
    is_union_territory  BOOLEAN DEFAULT FALSE,
    region              TEXT,                          -- North/South/East/West/Central/NE
    created_at          TIMESTAMPTZ DEFAULT NOW()
);



CREATE TABLE districts (
    district_lgd_code   VARCHAR(10) PRIMARY KEY,
    district_census_code VARCHAR(10),
    state_code          VARCHAR(2) NOT NULL REFERENCES states(state_code),
    district_name       TEXT NOT NULL,
    district_name_normalized TEXT NOT NULL,
    is_pilot_active     BOOLEAN DEFAULT FALSE,          -- flag: is this district in your active pilot?
    data_completeness_pct NUMERIC(5,2) DEFAULT 0,       -- % of villages with full data — dashboard metric
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_districts_state ON districts(state_code);
CREATE INDEX idx_districts_name_trgm ON districts USING gin (district_name_normalized gin_trgm_ops);

-- SUBDISTRICTS / BLOCKS
CREATE TABLE subdistricts (
    subdistrict_lgd_code VARCHAR(10) PRIMARY KEY,
    district_lgd_code    VARCHAR(10) NOT NULL REFERENCES districts(district_lgd_code),
    subdistrict_name     TEXT NOT NULL,
    subdistrict_name_normalized TEXT NOT NULL,
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_subdistricts_district ON subdistricts(district_lgd_code);

-- VILLAGES — the core identity node everything else attaches to
CREATE TABLE villages (
    village_lgd_code     VARCHAR(15) PRIMARY KEY,
    village_census_2011_code VARCHAR(15),
    subdistrict_lgd_code VARCHAR(10) NOT NULL REFERENCES subdistricts(subdistrict_lgd_code),
    district_lgd_code    VARCHAR(10) NOT NULL REFERENCES districts(district_lgd_code),  -- denormalized for fast queries
    state_code           VARCHAR(2)  NOT NULL REFERENCES states(state_code),            -- denormalized
    village_name         TEXT NOT NULL,
    village_name_normalized TEXT NOT NULL,
    local_body_code      VARCHAR(15),
    local_body_name      TEXT,
    is_pilot_active       BOOLEAN DEFAULT FALSE,
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_villages_district ON villages(district_lgd_code);
CREATE INDEX idx_villages_subdistrict ON villages(subdistrict_lgd_code);
CREATE INDEX idx_villages_name_trgm ON villages USING gin (village_name_normalized gin_trgm_ops);

-- LOCATIONS — geospatial point layer (1:1 with villages, separated for clean geom indexing)
CREATE TABLE locations (
    location_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    village_lgd_code      VARCHAR(15) UNIQUE REFERENCES villages(village_lgd_code),
    latitude              DOUBLE PRECISION NOT NULL,
    longitude             DOUBLE PRECISION NOT NULL,
    geom                  GEOMETRY(Point, 4326) NOT NULL,
    coordinate_source     TEXT NOT NULL,               -- 'postal_office_proximity' | 'geonames' | 'field_verified'
    coordinate_accuracy   TEXT,                         -- 'high' | 'medium' | 'low'
    created_at             TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_locations_geom ON locations USING GIST(geom);

-- Trigger to auto-populate geom from lat/lon on insert/update
CREATE OR REPLACE FUNCTION set_geom() RETURNS TRIGGER AS $$
BEGIN
    NEW.geom = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    RETURN NEW;
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_set_geom BEFORE INSERT OR UPDATE ON locations
    FOR EACH ROW EXECUTE FUNCTION set_geom();

-- ============================================================================
-- 1.2 POPULATION & ECONOMIC LAYER
-- ============================================================================

-- POPULATION STATS — village-level where available, district fallback tracked explicitly
CREATE TABLE population_stats (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    village_lgd_code       VARCHAR(15) REFERENCES villages(village_lgd_code),
    district_lgd_code      VARCHAR(10) REFERENCES districts(district_lgd_code),
    geographic_level       TEXT NOT NULL,               -- 'village' | 'district' | 'state' — CRITICAL: always know your granularity
    source                 TEXT NOT NULL,                -- 'Census PCA 2011' | 'SECC 2011'
    source_year             INT NOT NULL,
    total_population        INT,
    male_population          INT,
    female_population        INT,
    total_households          INT,
    sex_ratio                 NUMERIC(6,2),
    data_quality              TEXT DEFAULT 'medium',      -- 'high'|'medium'|'low'
    created_at                 TIMESTAMPTZ DEFAULT NOW(),
    CHECK (geographic_level IN ('village','subdistrict','district','state'))
);

CREATE INDEX idx_popstats_village ON population_stats(village_lgd_code);
CREATE INDEX idx_popstats_district ON population_stats(district_lgd_code);

-- STATE ECONOMIC PROFILE — SECC-derived (income bands, deprivation, land ownership)
CREATE TABLE state_economic_profile (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state_code                VARCHAR(2) NOT NULL REFERENCES states(state_code),
    district_lgd_code          VARCHAR(10) REFERENCES districts(district_lgd_code),  -- NULL if state-level only
    geographic_level             TEXT NOT NULL,          -- 'state' | 'district' | 'village'
    total_households               INT,
    deprived_households_pct         NUMERIC(5,2),
    income_lt_5000_pct              NUMERIC(5,2),
    income_5k_10k_pct                NUMERIC(5,2),
    income_gt_10k_pct                 NUMERIC(5,2),
    literacy_rate_pct                  NUMERIC(5,2),
    land_ownership_pct                  NUMERIC(5,2),
    source                                TEXT DEFAULT 'SECC 2011',
    source_year                            INT DEFAULT 2011,
    created_at                              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_econprofile_state ON state_economic_profile(state_code);
CREATE INDEX idx_econprofile_district ON state_economic_profile(district_lgd_code);


CREATE TABLE purchasing_power_bands (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state_code          VARCHAR(2) NOT NULL REFERENCES states(state_code),
    rural_urban          TEXT NOT NULL,                  -- 'rural' | 'urban'
    monthly_pcc_expenditure NUMERIC(10,2),                -- MPCE in rupees
    band_classification    TEXT,                          -- 'low' | 'medium' | 'high' — computed vs national avg
    source                   TEXT DEFAULT 'HCES 2023-24',
    survey_year                INT DEFAULT 2024,
    created_at                  TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 1.3 CONNECTIVITY & INFRASTRUCTURE LAYER
-- ============================================================================

-- RURAL ASSETS — PMGSY facilities (markets, health, schools, veterinary, banks)
CREATE TABLE rural_assets (
    asset_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_type            TEXT NOT NULL,                 -- 'market'|'health'|'school'|'veterinary'|'bank'|'milk_collection_point'
    facility_category      TEXT,                          -- finer-grained sub-type
    asset_name               TEXT,
    district_lgd_code          VARCHAR(10) REFERENCES districts(district_lgd_code),
    latitude                     DOUBLE PRECISION,
    longitude                     DOUBLE PRECISION,
    geom                            GEOMETRY(Point, 4326),
    road_class                        TEXT,               -- connectivity metadata
    source                              TEXT DEFAULT 'PMGSY',
    source_date                          DATE,
    created_at                             TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_assets_geom ON rural_assets USING GIST(geom);
CREATE INDEX idx_assets_district ON rural_assets(district_lgd_code);
CREATE INDEX idx_assets_type ON rural_assets(asset_type);
CREATE TRIGGER trg_assets_geom BEFORE INSERT OR UPDATE ON rural_assets
    FOR EACH ROW EXECUTE FUNCTION set_geom();


-- RURAL ROADS — PMGSY line geometry, for connectivity scoring
CREATE TABLE rural_roads (
    road_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    road_name              TEXT,
    road_class               TEXT,                        -- 'all-weather' | 'seasonal' etc
    district_lgd_code          VARCHAR(10) REFERENCES districts(district_lgd_code),
    geom                          GEOMETRY(LineString, 4326),
    source                          TEXT DEFAULT 'PMGSY',
    source_date                      DATE,
    created_at                         TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_roads_geom ON rural_roads USING GIST(geom);
CREATE INDEX idx_roads_district ON rural_roads(district_lgd_code);

-- ============================================================================
-- 1.4 BUSINESS, COMPETITION & PRICING LAYER
-- ============================================================================

-- DISTRICT BUSINESS SUMMARY — Udyam/MSME, district-level aggregate (your CSV as-is)
CREATE TABLE district_business_summary (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    district_lgd_code       VARCHAR(10) NOT NULL REFERENCES districts(district_lgd_code),
    sector                    TEXT,                       -- if sector-level breakdown available
    micro_count                 INT DEFAULT 0,
    small_count                   INT DEFAULT 0,
    medium_count                    INT DEFAULT 0,
    manufacturing_count               INT DEFAULT 0,
    service_count                       INT DEFAULT 0,
    trading_count                        INT DEFAULT 0,
    total_registered                       INT DEFAULT 0,
    reference_date                           DATE,
    source                                     TEXT DEFAULT 'Udyam Registration',
    created_at                                   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_bizsummary_district ON district_business_summary(district_lgd_code);


CREATE TABLE category_config (
    category_code         TEXT PRIMARY KEY,               -- 'dairy'|'grocery'|'tailoring'
    display_name            TEXT NOT NULL,
    target_segments             JSONB,                     -- ["households","tea_shops","restaurants"]
    relevant_commodities           JSONB,                  -- ["milk","curd","ghee"]
    required_facilities               JSONB,               -- ["milk_collection_point","veterinary_facility"]
    risk_factors                         JSONB,             -- ["feed_cost","animal_health","seasonality"]
    competitor_categories                   JSONB,          -- ["dairy_shop","milk_vendor"]
    pricing_method                            TEXT,          -- 'local_price_plus_cost_margin'
    demand_formula_params                        JSONB,      -- {"purchase_freq_per_year": 1.5, "participation_rate": 0.55}
    threat_thresholds                              JSONB,    -- {"supply_chain_km": 15, "competitor_density_high": 5}
    is_active                                        BOOLEAN DEFAULT TRUE,
    created_at                                          TIMESTAMPTZ DEFAULT NOW(),
    updated_at                                            TIMESTAMPTZ DEFAULT NOW()
);


CREATE TABLE businesses (
    business_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                      TEXT,
    category                    TEXT NOT NULL REFERENCES category_config(category_code), -- FIXED: was comment-only, now a real FK
    village_lgd_code               VARCHAR(15) REFERENCES villages(village_lgd_code),
    district_lgd_code                 VARCHAR(10) REFERENCES districts(district_lgd_code),
    latitude                             DOUBLE PRECISION,
    longitude                             DOUBLE PRECISION,
    geom                                    GEOMETRY(Point, 4326),
    registration_type                        TEXT,          -- 'formal_udyam'|'osm_mapped'|'field_survey'|'district_estimate'
    confidence                                 TEXT DEFAULT 'medium',  -- 'high'|'medium'|'low'
    source                                       TEXT NOT NULL,
    source_date                                    DATE,
    created_at                                       TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_businesses_geom ON businesses USING GIST(geom);
CREATE INDEX idx_businesses_category ON businesses(category);
CREATE INDEX idx_businesses_village ON businesses(village_lgd_code);
CREATE TRIGGER trg_businesses_geom BEFORE INSERT OR UPDATE ON businesses
    FOR EACH ROW EXECUTE FUNCTION set_geom();

-- MARKET PRICES — AGMARKNET commodity-level daily/periodic prices
CREATE TABLE market_prices (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state_code             VARCHAR(2) REFERENCES states(state_code),
    district_lgd_code         VARCHAR(10) REFERENCES districts(district_lgd_code),
    market_name                  TEXT,
    commodity                       TEXT NOT NULL,
    variety                           TEXT,
    price_date                          DATE NOT NULL,
    min_price                             NUMERIC(10,2),
    max_price                               NUMERIC(10,2),
    modal_price                               NUMERIC(10,2),
    arrival_quantity                            NUMERIC(12,2),
    source                                         TEXT DEFAULT 'AGMARKNET',
    created_at                                       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_prices_district_date ON market_prices(district_lgd_code, price_date);
CREATE INDEX idx_prices_commodity ON market_prices(commodity);

-- PRICE INDEX — MoSPI CPI, state/UT-level, monthly time series
CREATE TABLE price_index (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state_code            VARCHAR(2) REFERENCES states(state_code),   -- NULL = all-India row
    division                 TEXT,                        -- CPI sub-group, e.g. 'Food and beverages'
    month_year                  DATE NOT NULL,             -- store as first-of-month
    general_index                  NUMERIC(8,2),
    inflation_rate_pct                NUMERIC(6,2),
    rural_urban_combined                 TEXT DEFAULT 'combined',  -- 'rural'|'urban'|'combined'
    source                                 TEXT DEFAULT 'MoSPI CPI',
    created_at                               TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(state_code, division, month_year, rural_urban_combined)
);

CREATE INDEX idx_priceindex_state_month ON price_index(state_code, month_year);

-- ============================================================================
-- 1.5 CROWD-SOURCED VALIDATION LAYER
-- ============================================================================

-- FIELD OBSERVATIONS — user/field-worker-submitted ground truth to fill data gaps
CREATE TABLE field_observations (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    village_lgd_code        VARCHAR(15) NOT NULL REFERENCES villages(village_lgd_code),
    category                   TEXT NOT NULL,
    observation_type              TEXT NOT NULL,           -- 'competitor_count'|'nearest_market'|'selling_price'|'road_usable_monsoon'
    observed_value_numeric           NUMERIC,
    observed_value_text                 TEXT,
    radius_km                             NUMERIC(5,2),     -- if applicable (e.g. "competitors within 5km")
    observer_type                           TEXT,           -- 'end_user'|'field_worker'|'verified_partner'
    observer_id                               UUID,          -- FK to users, nullable for anonymous
    observation_date                            DATE DEFAULT CURRENT_DATE,
    confidence                                    TEXT DEFAULT 'unverified', -- 'unverified'|'single_report'|'cross_verified'
    created_at                                      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_fieldobs_village ON field_observations(village_lgd_code);
CREATE INDEX idx_fieldobs_type ON field_observations(observation_type);

-- ============================================================================
-- 1.6 CONFIGURATION & APPLICATION LAYER
-- ============================================================================

-- USERS — application accounts (entrepreneurs, field workers, admins)
CREATE TABLE users (
    user_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number             TEXT UNIQUE,
    name                        TEXT,
    preferred_language             TEXT DEFAULT 'en',
    role                              TEXT DEFAULT 'entrepreneur', -- 'entrepreneur'|'field_worker'|'admin'
    home_village_lgd_code               VARCHAR(15) REFERENCES villages(village_lgd_code),
    created_at                             TIMESTAMPTZ DEFAULT NOW(),
    last_active_at                            TIMESTAMPTZ
);

-- FEASIBILITY REPORTS — cached final output (input_hash enables caching)
CREATE TABLE feasibility_reports (
    report_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                   UUID REFERENCES users(user_id),
    village_lgd_code             VARCHAR(15) NOT NULL REFERENCES villages(village_lgd_code),
    business_category               TEXT NOT NULL REFERENCES category_config(category_code),
    radius_km                          NUMERIC(5,2) DEFAULT 10,
    margin_capital                        NUMERIC(12,2),      -- from Module 2 input, nullable
    input_hash                               TEXT NOT NULL,   -- hash(village+category+radius+capital) for cache lookup
    report_json                                JSONB NOT NULL, -- full structured output, doc's schema
    overall_feasibility_score                     NUMERIC(5,2),
    confidence_score                                 NUMERIC(5,2),
    status                                              TEXT DEFAULT 'completed', -- 'queued'|'processing'|'completed'|'failed'
    created_at                                             TIMESTAMPTZ DEFAULT NOW(),
    expires_at                                               TIMESTAMPTZ         -- cache invalidation
);
CREATE INDEX idx_reports_hash ON feasibility_reports(input_hash);
CREATE INDEX idx_reports_village ON feasibility_reports(village_lgd_code);
CREATE INDEX idx_reports_user ON feasibility_reports(user_id);

-- FINANCIAL CALCULATIONS — Module 2 output log
CREATE TABLE financial_calculations (
    calc_id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                   UUID REFERENCES users(user_id),
    margin_capital               NUMERIC(12,2) NOT NULL,
    project_cost                    NUMERIC(12,2) NOT NULL,
    max_loan_amount                    NUMERIC(12,2) NOT NULL,
    scheme_selected                       TEXT NOT NULL,      -- 'Micro Finance Scheme'|'Term Loan Scheme'
    interest_rate                            NUMERIC(5,2),
    tenure_years                                INT,
    moratorium_months                              INT,
    emi_amount                                        NUMERIC(12,2),
    created_at                                           TIMESTAMPTZ DEFAULT NOW()
);

-- DATA SOURCE REGISTRY — the "data dictionary" the doc mandates
CREATE TABLE data_source_registry (
    source_id              TEXT PRIMARY KEY,               -- 'census_pca_2011', 'agmarknet', etc
    source_name               TEXT NOT NULL,
    meaning                      TEXT,
    geographic_level                TEXT,
    unit                                TEXT,
    update_frequency                       TEXT,
    limitations                               TEXT,
    official_url                                 TEXT,
    last_ingested_at                                TIMESTAMPTZ
);

