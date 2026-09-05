CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "pgcrypto"; -- gen_random_uuid()

-- ============================================================================
-- SECTION 1: GEOGRAPHY (Reference / Identity Layer)
-- ============================================================================

CREATE TABLE states (
    state_code            VARCHAR(2)  PRIMARY KEY,
    census_2011_code      VARCHAR(2),
    state_name            TEXT NOT NULL,
    state_name_normalized TEXT NOT NULL,
    is_union_territory    BOOLEAN DEFAULT FALSE,
    region                TEXT,
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE districts (
    district_lgd_code      VARCHAR(10) PRIMARY KEY,
    district_census_code   VARCHAR(10),
    state_code             VARCHAR(2) NOT NULL REFERENCES states(state_code),
    district_name          TEXT NOT NULL,
    district_name_normalized TEXT NOT NULL,
    is_pilot_active         BOOLEAN DEFAULT FALSE,
    data_completeness_pct   NUMERIC(5,2) DEFAULT 0,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_districts_state ON districts(state_code);
CREATE INDEX idx_districts_name_trgm ON districts USING gin (district_name_normalized gin_trgm_ops);

CREATE TABLE subdistricts (
    subdistrict_lgd_code VARCHAR(10) PRIMARY KEY,
    district_lgd_code    VARCHAR(10) NOT NULL REFERENCES districts(district_lgd_code),
    subdistrict_name     TEXT NOT NULL,
    subdistrict_name_normalized TEXT NOT NULL,
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_subdistricts_district ON subdistricts(district_lgd_code);

CREATE TABLE villages (
    village_lgd_code          VARCHAR(15) PRIMARY KEY,
    village_census_2011_code  VARCHAR(15),
    subdistrict_lgd_code      VARCHAR(10) NOT NULL REFERENCES subdistricts(subdistrict_lgd_code),
    district_lgd_code         VARCHAR(10) NOT NULL REFERENCES districts(district_lgd_code),
    state_code                VARCHAR(2)  NOT NULL REFERENCES states(state_code),
    village_name              TEXT NOT NULL,
    village_name_normalized   TEXT NOT NULL,
    local_body_code           VARCHAR(15),
    local_body_name           TEXT,
    is_pilot_active           BOOLEAN DEFAULT FALSE,
    created_at                TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_villages_district ON villages(district_lgd_code);

CREATE INDEX idx_villages_subdistrict ON villages(subdistrict_lgd_code);

CREATE INDEX idx_villages_name_trgm ON villages USING gin (village_name_normalized gin_trgm_ops);

CREATE TABLE locations (
    location_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    village_lgd_code     VARCHAR(15) UNIQUE REFERENCES villages(village_lgd_code),
    latitude              DOUBLE PRECISION NOT NULL,
    longitude             DOUBLE PRECISION NOT NULL,
    geom                  GEOMETRY(Point, 4326) NOT NULL,
    coordinate_source     TEXT NOT NULL,
    coordinate_accuracy   TEXT,
    created_at            TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_locations_geom ON locations USING GIST(geom);

CREATE OR REPLACE FUNCTION set_geom() RETURNS TRIGGER AS $$
BEGIN
    NEW.geom = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    RETURN NEW;
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_set_geom BEFORE INSERT OR UPDATE ON locations
    FOR EACH ROW EXECUTE FUNCTION set_geom();


CREATE TABLE geographic_mappings (
    mapping_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type         TEXT NOT NULL,          -- 'state'|'district'|'subdistrict'|'village'
    canonical_code       TEXT NOT NULL,          -- our LGD-style code
    source_id             TEXT NOT NULL,          -- e.g. 'census_2011', 'osm'
    source_entity_type     TEXT,
    source_code             TEXT NOT NULL,
    source_name               TEXT,
    match_method               TEXT,             -- 'exact'|'fuzzy'|'manual'
    match_confidence            NUMERIC(4,3),
    manually_verified             BOOLEAN DEFAULT FALSE,
    valid_from                     DATE,
    valid_to                         DATE,
    created_at                        TIMESTAMPTZ DEFAULT NOW(),
    updated_at                          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_geomap_canonical ON geographic_mappings(entity_type, canonical_code);

-- ============================================================================
-- SECTION 2: POPULATION & ECONOMIC LAYER
-- ============================================================================

CREATE TABLE population_stats (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    village_lgd_code    VARCHAR(15) REFERENCES villages(village_lgd_code),
    district_lgd_code   VARCHAR(10) REFERENCES districts(district_lgd_code),
    geographic_level    TEXT NOT NULL,
    source              TEXT NOT NULL,
    source_year         INT NOT NULL,
    total_population    INT,
    male_population     INT,
    female_population   INT,
    total_households    INT,
    sex_ratio           NUMERIC(6,2),
    data_quality        TEXT DEFAULT 'medium',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    CHECK (geographic_level IN ('village','subdistrict','district','state')),
    CHECK (
        (geographic_level = 'village'     AND village_lgd_code  IS NOT NULL) OR
        (geographic_level = 'district'    AND district_lgd_code IS NOT NULL) OR
        (geographic_level IN ('subdistrict','state'))
    )
);

CREATE INDEX idx_popstats_village ON population_stats(village_lgd_code);

CREATE INDEX idx_popstats_district ON population_stats(district_lgd_code);

CREATE TABLE state_economic_profile (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state_code               VARCHAR(2) NOT NULL REFERENCES states(state_code),
    district_lgd_code        VARCHAR(10) REFERENCES districts(district_lgd_code),
    geographic_level         TEXT NOT NULL,
    total_households         INT,
    deprived_households_pct  NUMERIC(5,2),
    income_lt_5000_pct       NUMERIC(5,2),
    income_5k_10k_pct        NUMERIC(5,2),
    income_gt_10k_pct        NUMERIC(5,2),
    literacy_rate_pct        NUMERIC(5,2),
    land_ownership_pct       NUMERIC(5,2),
    source                   TEXT DEFAULT 'SECC 2011',
    source_year              INT DEFAULT 2011,
    created_at               TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE purchasing_power_bands (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state_code               VARCHAR(2) NOT NULL REFERENCES states(state_code),
    rural_urban              TEXT NOT NULL,
    monthly_pcc_expenditure  NUMERIC(10,2),
    band_classification      TEXT,
    source                   TEXT DEFAULT 'HCES 2023-24',
    survey_year              INT DEFAULT 2024,
    created_at               TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- SECTION 3: CONNECTIVITY & INFRASTRUCTURE
-- ============================================================================

CREATE TABLE rural_assets (
    asset_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_type         TEXT NOT NULL,
    facility_category  TEXT,
    asset_name         TEXT,
    village_lgd_code   VARCHAR(15) REFERENCES villages(village_lgd_code),
    district_lgd_code  VARCHAR(10) REFERENCES districts(district_lgd_code),
    latitude           DOUBLE PRECISION,
    longitude          DOUBLE PRECISION,
    geom               GEOMETRY(Point, 4326),
    road_class         TEXT,
    source             TEXT DEFAULT 'PMGSY',
    source_date        DATE,
    created_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_assets_geom ON rural_assets USING GIST(geom);

CREATE INDEX idx_assets_district ON rural_assets(district_lgd_code);

CREATE INDEX idx_assets_type ON rural_assets(asset_type);

CREATE TRIGGER trg_assets_geom BEFORE INSERT OR UPDATE ON rural_assets
    FOR EACH ROW EXECUTE FUNCTION set_geom();


CREATE TABLE rural_roads (
    road_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    road_name          TEXT,
    road_class         TEXT,
    district_lgd_code  VARCHAR(10) REFERENCES districts(district_lgd_code),
    geom               GEOMETRY(LineString, 4326),
    road_condition     TEXT,
    source             TEXT DEFAULT 'PMGSY',
    source_date        DATE,
    created_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_roads_geom ON rural_roads USING GIST(geom);

CREATE INDEX idx_roads_district ON rural_roads(district_lgd_code);

-- ============================================================================
-- SECTION 4: BUSINESS, COMPETITION & PRICING
-- ============================================================================

CREATE TABLE business_categories (
    category_code         TEXT PRIMARY KEY,
    category_name         TEXT NOT NULL,
    parent_category_code  TEXT REFERENCES business_categories(category_code),
    description           TEXT,
    is_active             BOOLEAN DEFAULT TRUE,
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    updated_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE district_business_summary (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    district_lgd_code     VARCHAR(10) NOT NULL REFERENCES districts(district_lgd_code),
    sector                TEXT,
    micro_count           INT DEFAULT 0,
    small_count           INT DEFAULT 0,
    medium_count          INT DEFAULT 0,
    manufacturing_count   INT DEFAULT 0,
    service_count         INT DEFAULT 0,
    trading_count         INT DEFAULT 0,
    total_registered      INT DEFAULT 0,
    reference_date        DATE,
    source                TEXT DEFAULT 'Udyam Registration',
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_bizsummary_district ON district_business_summary(district_lgd_code);

CREATE TABLE businesses (
    business_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT,
    category            TEXT NOT NULL REFERENCES business_categories(category_code),
    village_lgd_code    VARCHAR(15) REFERENCES villages(village_lgd_code),
    district_lgd_code   VARCHAR(10) REFERENCES districts(district_lgd_code),
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    geom                GEOMETRY(Point, 4326),
    registration_type   TEXT,   -- 'formal_udyam'|'osm_mapped'|'field_survey'|'district_estimate'
    verification_status TEXT DEFAULT 'source_imported',
    confidence          TEXT DEFAULT 'medium',
    source              TEXT NOT NULL,
    source_date         DATE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_businesses_geom ON businesses USING GIST(geom);

CREATE INDEX idx_businesses_category ON businesses(category);

CREATE INDEX idx_businesses_village ON businesses(village_lgd_code);

CREATE TRIGGER trg_businesses_geom BEFORE INSERT OR UPDATE ON businesses
    FOR EACH ROW EXECUTE FUNCTION set_geom();


CREATE TABLE business_sources (
    business_source_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id          UUID NOT NULL REFERENCES businesses(business_id),
    source_id             TEXT NOT NULL,
    source_record_id       TEXT,
    source_date             DATE,
    source_payload            JSONB,
    confidence_level           TEXT,
    created_at                  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_bizsources_business ON business_sources(business_id);

CREATE TABLE market_prices (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state_code         VARCHAR(2) REFERENCES states(state_code),
    district_lgd_code  VARCHAR(10) REFERENCES districts(district_lgd_code),
    market_name        TEXT,
    commodity          TEXT NOT NULL,
    variety            TEXT,
    price_date         DATE NOT NULL,
    min_price          NUMERIC(10,2),
    max_price          NUMERIC(10,2),
    modal_price        NUMERIC(10,2),
    arrival_quantity   NUMERIC(12,2),
    source             TEXT DEFAULT 'AGMARKNET',
    created_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_prices_district_date ON market_prices(district_lgd_code, price_date);

CREATE INDEX idx_prices_commodity ON market_prices(commodity);

CREATE TABLE price_index (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state_code             VARCHAR(2) REFERENCES states(state_code),
    division               TEXT,
    month_year             DATE NOT NULL,
    general_index          NUMERIC(8,2),
    inflation_rate_pct     NUMERIC(6,2),
    rural_urban_combined   TEXT DEFAULT 'combined',
    source                 TEXT DEFAULT 'MoSPI CPI',
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(state_code, division, month_year, rural_urban_combined)
);
CREATE INDEX idx_priceindex_state_month ON price_index(state_code, month_year);

CREATE TABLE government_schemes (
    scheme_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scheme_name           TEXT NOT NULL,
    scheme_code           TEXT,
    implementing_agency   TEXT,
    scheme_level          TEXT,       -- 'central'|'state'
    description           TEXT,
    official_url          TEXT,
    valid_from            DATE,
    valid_to              DATE,
    is_active             BOOLEAN DEFAULT TRUE,
    source_id             TEXT,
    source_date           DATE,
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE scheme_business_categories (
    scheme_id      UUID REFERENCES government_schemes(scheme_id),
    category_code  TEXT REFERENCES business_categories(category_code),
    PRIMARY KEY (scheme_id, category_code)
);

-- ============================================================================
-- SECTION 5: CROWD-SOURCED VALIDATION LAYER
-- ============================================================================

CREATE TABLE field_observations (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    village_lgd_code         VARCHAR(15) NOT NULL REFERENCES villages(village_lgd_code),
    category                 TEXT,
    observation_type         TEXT NOT NULL,
    observed_value_numeric   NUMERIC,
    observed_value_text      TEXT,
    radius_km                NUMERIC(5,2),
    observer_type            TEXT,       -- 'end_user'|'field_worker'|'verified_partner'
    observer_id              UUID,
    observation_date         DATE DEFAULT CURRENT_DATE,
    confidence               TEXT DEFAULT 'unverified',
    created_at               TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_fieldobs_village ON field_observations(village_lgd_code);

CREATE INDEX idx_fieldobs_type ON field_observations(observation_type);

-- ============================================================================
-- SECTION 6: CONFIGURATION & APPLICATION LAYER
-- ============================================================================

CREATE TABLE category_config (
    category_code           TEXT PRIMARY KEY REFERENCES business_categories(category_code),
    display_name            TEXT NOT NULL,
    target_segments         JSONB,
    relevant_commodities    JSONB,
    required_facilities     JSONB,
    risk_factors            JSONB,
    competitor_categories   JSONB,
    pricing_method          TEXT,
    demand_formula_params   JSONB,
    threat_thresholds       JSONB,
    is_active               BOOLEAN DEFAULT TRUE,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE users (
    user_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number         TEXT UNIQUE,
    name                 TEXT,
    preferred_language   TEXT DEFAULT 'en',
    role                 TEXT DEFAULT 'entrepreneur',   -- 'entrepreneur'|'field_worker'|'admin'
    home_village_lgd_code VARCHAR(15) REFERENCES villages(village_lgd_code),
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    last_active_at       TIMESTAMPTZ
);

-- ============================================================================
-- SECTION 7: ASSESSMENT & ANALYSIS PIPELINE
-- ============================================================================

CREATE TABLE business_assessments (
    assessment_id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                           UUID REFERENCES users(user_id),
    village_lgd_code                  VARCHAR(15) NOT NULL REFERENCES villages(village_lgd_code),
    available_capital                 NUMERIC(12,2),
    monthly_income                    NUMERIC(12,2),
    existing_monthly_loan_payment     NUMERIC(12,2),
    assessment_status                 TEXT DEFAULT 'draft',
    created_at                        TIMESTAMPTZ DEFAULT NOW(),
    updated_at                        TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE assessment_business_options (
    option_id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id              UUID NOT NULL REFERENCES business_assessments(assessment_id),
    category_code              TEXT NOT NULL REFERENCES business_categories(category_code),
    user_interest_rank         INT,
    is_selected_for_analysis   BOOLEAN DEFAULT TRUE,
    created_at                 TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE financial_assessments (
    financial_assessment_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id                UUID REFERENCES business_assessments(assessment_id),
    option_id                     UUID REFERENCES assessment_business_options(option_id),
    estimated_project_cost         NUMERIC(12,2),
    available_capital               NUMERIC(12,2),
    suggested_loan_amount            NUMERIC(12,2),
    annual_interest_rate              NUMERIC(5,2),
    loan_tenure_months                 INT,
    monthly_emi                          NUMERIC(12,2),
    estimated_monthly_revenue              NUMERIC(12,2),
    estimated_monthly_expenses               NUMERIC(12,2),
    estimated_monthly_surplus                  NUMERIC(12,2),
    break_even_months                            INT,
    calculation_version                            TEXT,
    created_at                                       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE financial_scenarios (
    scenario_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    financial_assessment_id   UUID NOT NULL REFERENCES financial_assessments(financial_assessment_id),
    scenario_type             TEXT NOT NULL,     -- 'conservative'|'expected'|'optimistic'
    revenue_multiplier        NUMERIC(4,2),
    expense_multiplier        NUMERIC(4,2),
    estimated_revenue         NUMERIC(12,2),
    estimated_expenses        NUMERIC(12,2),
    estimated_surplus         NUMERIC(12,2),
    break_even_months         INT,
    created_at                TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE market_opportunity_analysis (
    market_analysis_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id        UUID REFERENCES business_assessments(assessment_id),
    option_id             UUID REFERENCES assessment_business_options(option_id),
    population_score        NUMERIC(5,2),
    demand_score              NUMERIC(5,2),
    market_access_score        NUMERIC(5,2),
    overall_market_score         NUMERIC(5,2),
    confidence_score                NUMERIC(5,2),
    calculation_version                TEXT,
    calculated_at                        TIMESTAMPTZ,
    created_at                             TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE competition_analysis (
    competition_analysis_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id             UUID REFERENCES business_assessments(assessment_id),
    option_id                  UUID REFERENCES assessment_business_options(option_id),
    competitor_count             INT,
    search_radius_meters           INT,
    competition_score                NUMERIC(5,2),
    competition_level                  TEXT,
    confidence_score                     NUMERIC(5,2),
    calculation_version                    TEXT,
    calculated_at                            TIMESTAMPTZ,
    created_at                                 TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE infrastructure_analysis (
    infrastructure_analysis_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id                UUID REFERENCES business_assessments(assessment_id),
    option_id                     UUID REFERENCES assessment_business_options(option_id),
    infrastructure_score            NUMERIC(5,2),
    available_assets                  JSONB,
    missing_assets                      JSONB,
    confidence_score                      NUMERIC(5,2),
    calculation_version                     TEXT,
    calculated_at                             TIMESTAMPTZ,
    created_at                                  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE risk_analysis (
    risk_analysis_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id                UUID REFERENCES business_assessments(assessment_id),
    option_id                     UUID REFERENCES assessment_business_options(option_id),
    market_risk_score               NUMERIC(5,2),
    financial_risk_score              NUMERIC(5,2),
    infrastructure_risk_score           NUMERIC(5,2),
    data_risk_score                       NUMERIC(5,2),
    overall_risk_score                      NUMERIC(5,2),
    risk_level                                TEXT,
    risk_factors                                JSONB,
    calculation_version                           TEXT,
    calculated_at                                   TIMESTAMPTZ,
    created_at                                        TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE scheme_matches (
    scheme_match_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id        UUID REFERENCES business_assessments(assessment_id),
    option_id             UUID REFERENCES assessment_business_options(option_id),
    scheme_id               UUID REFERENCES government_schemes(scheme_id),
    eligibility_status         TEXT DEFAULT 'potentially_eligible',
    eligibility_score            NUMERIC(5,2),
    eligibility_reasons             JSONB,
    calculated_at                     TIMESTAMPTZ,
    created_at                          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE scoring_config (
    scoring_version   TEXT PRIMARY KEY,
    config_name       TEXT,
    effective_from    DATE,
    effective_to      DATE,
    is_active         BOOLEAN DEFAULT TRUE,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE scoring_weights (
    weight_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scoring_version   TEXT NOT NULL REFERENCES scoring_config(scoring_version),
    score_component   TEXT NOT NULL,   -- 'market'|'financial'|'competition'|'risk'|'infrastructure'
    weight            NUMERIC(4,3) NOT NULL,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE business_viability_scores (
    viability_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id             UUID REFERENCES business_assessments(assessment_id),
    option_id                  UUID REFERENCES assessment_business_options(option_id),
    market_score                 NUMERIC(5,2),
    competition_score              NUMERIC(5,2),
    financial_score                  NUMERIC(5,2),
    risk_score                         NUMERIC(5,2),
    infrastructure_score                 NUMERIC(5,2),
    overall_score                          NUMERIC(5,2),
    recommendation_rank                      INT,
    recommendation_status                      TEXT,
    confidence_score                             NUMERIC(5,2),
    scoring_version                                TEXT REFERENCES scoring_config(scoring_version),
    calculated_at                                    TIMESTAMPTZ,
    created_at                                         TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE feasibility_reports (
    report_id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                    UUID REFERENCES users(user_id),
    assessment_id              UUID REFERENCES business_assessments(assessment_id),
    village_lgd_code           VARCHAR(15) NOT NULL REFERENCES villages(village_lgd_code),
    business_category          TEXT REFERENCES category_config(category_code),
    recommended_option_id      UUID REFERENCES assessment_business_options(option_id),
    radius_km                  NUMERIC(5,2) DEFAULT 10,
    margin_capital             NUMERIC(12,2),
    input_hash                 TEXT,
    report_status              TEXT DEFAULT 'completed',
    report_json                JSONB,
    summary                    TEXT,
    key_reasons                JSONB,
    key_risks                  JSONB,
    overall_feasibility_score  NUMERIC(5,2),
    confidence_score           NUMERIC(5,2),
    generated_at               TIMESTAMPTZ,
    created_at                 TIMESTAMPTZ DEFAULT NOW(),
    updated_at                 TIMESTAMPTZ DEFAULT NOW(),
    expires_at                 TIMESTAMPTZ
);
CREATE INDEX idx_reports_hash ON feasibility_reports(input_hash);
CREATE INDEX idx_reports_village ON feasibility_reports(village_lgd_code);
CREATE INDEX idx_reports_user ON feasibility_reports(user_id);

-- GramVenture correction: AI explanations separated from deterministic facts.
CREATE TABLE ai_explanations (
    explanation_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id     UUID REFERENCES business_assessments(assessment_id),
    report_id         UUID REFERENCES feasibility_reports(report_id),
    explanation_type  TEXT,   -- 'recommendation_reason'|'risk_explanation'|'financial_explanation'|'simple_language_summary'
    input_snapshot    JSONB,
    generated_text    TEXT,
    model_name        TEXT,
    prompt_version    TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE financial_calculations (
    calc_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              UUID REFERENCES users(user_id),
    margin_capital       NUMERIC(12,2) NOT NULL,
    project_cost         NUMERIC(12,2) NOT NULL,
    max_loan_amount      NUMERIC(12,2) NOT NULL,
    scheme_selected      TEXT,
    interest_rate        NUMERIC(5,2),
    tenure_years         INT,
    moratorium_months    INT,
    emi_amount           NUMERIC(12,2),
    created_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE field_validations (
    validation_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    village_lgd_code  VARCHAR(15) REFERENCES villages(village_lgd_code),
    business_id       UUID REFERENCES businesses(business_id),
    validation_type   TEXT,
    validation_result TEXT,
    validated_by      UUID REFERENCES users(user_id),
    validated_at      TIMESTAMPTZ,
    evidence_location TEXT,
    notes             TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- SECTION 8: DATA GOVERNANCE
-- ============================================================================

CREATE TABLE data_sources (
    source_id            TEXT PRIMARY KEY,
    source_name          TEXT NOT NULL,
    organization         TEXT,
    official_url         TEXT,
    update_frequency     TEXT,
    license_information  TEXT,
    limitations          TEXT,
    last_ingested_at     TIMESTAMPTZ,
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ingestion_runs (
    ingestion_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id             TEXT REFERENCES data_sources(source_id),
    dataset_name          TEXT,
    started_at            TIMESTAMPTZ,
    completed_at          TIMESTAMPTZ,
    status                TEXT,
    source_file_name      TEXT,
    source_file_checksum  TEXT,
    records_read          INT,
    records_inserted      INT,
    records_rejected      INT,
    error_log             TEXT,
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE data_quality_issues (
    issue_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingestion_id          UUID REFERENCES ingestion_runs(ingestion_id),
    severity              TEXT,
    entity_type           TEXT,
    source_record_reference TEXT,
    issue_type            TEXT,
    issue_details         TEXT,
    resolved              BOOLEAN DEFAULT FALSE,
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    updated_at            TIMESTAMPTZ DEFAULT NOW()
);

