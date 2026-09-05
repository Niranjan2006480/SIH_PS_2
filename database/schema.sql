-- 1.1 REFERENCE / IDENTITY LAYER

CREATE TABLE states (
    state_code          VARCHAR(2)  PRIMARY KEY,
    census_2011_code    VARCHAR(2),
    state_name          TEXT NOT NULL,
    state_name_normalized TEXT NOT NULL,
    is_union_territory  BOOLEAN DEFAULT FALSE,
    region              TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE districts (
    district_lgd_code   VARCHAR(10) PRIMARY KEY,
    district_census_code VARCHAR(10),
    state_code          VARCHAR(2) NOT NULL REFERENCES states(state_code),
    district_name       TEXT NOT NULL,
    district_name_normalized TEXT NOT NULL,
    is_pilot_active     BOOLEAN DEFAULT FALSE,
    data_completeness_pct NUMERIC(5,2) DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE subdistricts (
    subdistrict_lgd_code VARCHAR(10) PRIMARY KEY,
    district_lgd_code    VARCHAR(10) NOT NULL REFERENCES districts(district_lgd_code),
    subdistrict_name     TEXT NOT NULL,
    subdistrict_name_normalized TEXT NOT NULL,
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE villages (
    village_lgd_code     VARCHAR(15) PRIMARY KEY,
    village_census_2011_code VARCHAR(15),
    subdistrict_lgd_code VARCHAR(10) NOT NULL REFERENCES subdistricts(subdistrict_lgd_code),
    district_lgd_code    VARCHAR(10) NOT NULL REFERENCES districts(district_lgd_code),
    state_code           VARCHAR(2)  NOT NULL REFERENCES states(state_code),
    village_name         TEXT NOT NULL,
    village_name_normalized TEXT NOT NULL,
    local_body_code      VARCHAR(15),
    local_body_name      TEXT,
    is_pilot_active       BOOLEAN DEFAULT FALSE,
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE locations (
    location_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    village_lgd_code      VARCHAR(15) UNIQUE REFERENCES villages(village_lgd_code),
    latitude              DOUBLE PRECISION NOT NULL,
    longitude             DOUBLE PRECISION NOT NULL,
    geom                  GEOMETRY(Point, 4326) NOT NULL,
    coordinate_source     TEXT NOT NULL,
    coordinate_accuracy   TEXT,
    created_at             TIMESTAMPTZ DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION set_geom() RETURNS TRIGGER AS $$
BEGIN
    NEW.geom = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    RETURN NEW;
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_set_geom BEFORE INSERT OR UPDATE ON locations
    FOR EACH ROW EXECUTE FUNCTION set_geom();

-- 1.2 POPULATION & ECONOMIC LAYER

CREATE TABLE population_stats (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    village_lgd_code       VARCHAR(15) REFERENCES villages(village_lgd_code),
    district_lgd_code      VARCHAR(10) REFERENCES districts(district_lgd_code),
    geographic_level       TEXT NOT NULL,
    source                 TEXT NOT NULL,
    source_year             INT NOT NULL,
    total_population        INT,
    male_population          INT,
    female_population        INT,
    total_households          INT,
    sex_ratio                 NUMERIC(6,2),
    data_quality              TEXT DEFAULT 'medium',
    created_at                 TIMESTAMPTZ DEFAULT NOW(),
    CHECK (geographic_level IN ('village','subdistrict','district','state'))
);

CREATE TABLE state_economic_profile (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state_code                VARCHAR(2) NOT NULL REFERENCES states(state_code),
    district_lgd_code          VARCHAR(10) REFERENCES districts(district_lgd_code),
    geographic_level             TEXT NOT NULL,
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

CREATE TABLE purchasing_power_bands (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state_code          VARCHAR(2) NOT NULL REFERENCES states(state_code),
    rural_urban          TEXT NOT NULL,
    monthly_pcc_expenditure NUMERIC(10,2),
    band_classification    TEXT,
    source                   TEXT DEFAULT 'HCES 2023-24',
    survey_year                INT DEFAULT 2024,
    created_at                  TIMESTAMPTZ DEFAULT NOW()
);

-- 1.3 CONNECTIVITY & INFRASTRUCTURE LAYER

CREATE TABLE rural_assets (
    asset_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_type            TEXT NOT NULL,
    facility_category      TEXT,
    asset_name               TEXT,
    district_lgd_code          VARCHAR(10) REFERENCES districts(district_lgd_code),
    latitude                     DOUBLE PRECISION,
    longitude                     DOUBLE PRECISION,
    geom                            GEOMETRY(Point, 4326),
    road_class                        TEXT,
    source                              TEXT DEFAULT 'PMGSY',
    source_date                          DATE,
    created_at                             TIMESTAMPTZ DEFAULT NOW()
);

CREATE TRIGGER trg_assets_geom BEFORE INSERT OR UPDATE ON rural_assets
    FOR EACH ROW EXECUTE FUNCTION set_geom();

CREATE TABLE rural_roads (
    road_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    road_name              TEXT,
    road_class               TEXT,
    district_lgd_code          VARCHAR(10) REFERENCES districts(district_lgd_code),
    geom                          GEOMETRY(LineString, 4326),
    source                          TEXT DEFAULT 'PMGSY',
    source_date                      DATE,
    created_at                         TIMESTAMPTZ DEFAULT NOW()
);

-- 1.4 BUSINESS, COMPETITION & PRICING LAYER

CREATE TABLE district_business_summary (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    district_lgd_code       VARCHAR(10) NOT NULL REFERENCES districts(district_lgd_code),
    sector                    TEXT,
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

CREATE TABLE category_config (
    category_code         TEXT PRIMARY KEY,
    display_name            TEXT NOT NULL,
    target_segments             JSONB,
    relevant_commodities           JSONB,
    required_facilities               JSONB,
    risk_factors                         JSONB,
    competitor_categories                   JSONB,
    pricing_method                            TEXT,
    demand_formula_params                        JSONB,
    threat_thresholds                              JSONB,
    is_active                                        BOOLEAN DEFAULT TRUE,
    created_at                                          TIMESTAMPTZ DEFAULT NOW(),
    updated_at                                            TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE businesses (
    business_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                      TEXT,
    category                    TEXT NOT NULL REFERENCES category_config(category_code),
    village_lgd_code               VARCHAR(15) REFERENCES villages(village_lgd_code),
    district_lgd_code                 VARCHAR(10) REFERENCES districts(district_lgd_code),
    latitude                             DOUBLE PRECISION,
    longitude                             DOUBLE PRECISION,
    geom                                    GEOMETRY(Point, 4326),
    registration_type                        TEXT,
    confidence                                 TEXT DEFAULT 'medium',
    source                                       TEXT NOT NULL,
    source_date                                    DATE,
    created_at                                       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TRIGGER trg_businesses_geom BEFORE INSERT OR UPDATE ON businesses
    FOR EACH ROW EXECUTE FUNCTION set_geom();

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

CREATE TABLE price_index (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state_code            VARCHAR(2) REFERENCES states(state_code),
    division                 TEXT,
    month_year                  DATE NOT NULL,
    general_index                  NUMERIC(8,2),
    inflation_rate_pct                NUMERIC(6,2),
    rural_urban_combined                 TEXT DEFAULT 'combined',
    source                                 TEXT DEFAULT 'MoSPI CPI',
    created_at                               TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(state_code, division, month_year, rural_urban_combined)
);

-- 1.5 CROWD-SOURCED VALIDATION LAYER

CREATE TABLE field_observations (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    village_lgd_code        VARCHAR(15) NOT NULL REFERENCES villages(village_lgd_code),
    category                   TEXT NOT NULL,
    observation_type              TEXT NOT NULL,
    observed_value_numeric           NUMERIC,
    observed_value_text                 TEXT,
    radius_km                             NUMERIC(5,2),
    observer_type                           TEXT,
    observer_id                               UUID,
    observation_date                            DATE DEFAULT CURRENT_DATE,
    confidence                                    TEXT DEFAULT 'unverified',
    created_at                                      TIMESTAMPTZ DEFAULT NOW()
);

-- 1.6 CONFIGURATION & APPLICATION LAYER

CREATE TABLE users (
    user_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number             TEXT UNIQUE,
    name                        TEXT,
    preferred_language             TEXT DEFAULT 'en',
    role                              TEXT DEFAULT 'entrepreneur',
    home_village_lgd_code               VARCHAR(15) REFERENCES villages(village_lgd_code),
    created_at                             TIMESTAMPTZ DEFAULT NOW(),
    last_active_at                            TIMESTAMPTZ
);

CREATE TABLE feasibility_reports (
    report_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                   UUID REFERENCES users(user_id),
    village_lgd_code             VARCHAR(15) NOT NULL REFERENCES villages(village_lgd_code),
    business_category               TEXT NOT NULL REFERENCES category_config(category_code),
    radius_km                          NUMERIC(5,2) DEFAULT 10,
    margin_capital                        NUMERIC(12,2),
    input_hash                               TEXT NOT NULL,
    report_json                                JSONB NOT NULL,
    overall_feasibility_score                     NUMERIC(5,2),
    confidence_score                                 NUMERIC(5,2),
    status                                              TEXT DEFAULT 'completed',
    created_at                                             TIMESTAMPTZ DEFAULT NOW(),
    expires_at                                               TIMESTAMPTZ
);

CREATE TABLE financial_calculations (
    calc_id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                   UUID REFERENCES users(user_id),
    margin_capital               NUMERIC(12,2) NOT NULL,
    project_cost                    NUMERIC(12,2) NOT NULL,
    max_loan_amount                    NUMERIC(12,2) NOT NULL,
    scheme_selected                       TEXT NOT NULL,
    interest_rate                            NUMERIC(5,2),
    tenure_years                                INT,
    moratorium_months                              INT,
    emi_amount                                        NUMERIC(12,2),
    created_at                                           TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE data_source_registry (
    source_id              TEXT PRIMARY KEY,
    source_name               TEXT NOT NULL,
    meaning                      TEXT,
    geographic_level                TEXT,
    unit                                TEXT,
    update_frequency                       TEXT,
    limitations                               TEXT,
    official_url                                 TEXT,
    last_ingested_at                                TIMESTAMPTZ
);
