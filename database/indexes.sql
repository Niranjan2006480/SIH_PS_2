CREATE INDEX idx_districts_state ON districts(state_code);
CREATE INDEX idx_districts_name_trgm ON districts USING gin (district_name_normalized gin_trgm_ops);

CREATE INDEX idx_subdistricts_district ON subdistricts(district_lgd_code);

CREATE INDEX idx_villages_district ON villages(district_lgd_code);
CREATE INDEX idx_villages_subdistrict ON villages(subdistrict_lgd_code);
CREATE INDEX idx_villages_name_trgm ON villages USING gin (village_name_normalized gin_trgm_ops);

CREATE INDEX idx_locations_geom ON locations USING GIST(geom);

CREATE INDEX idx_popstats_village ON population_stats(village_lgd_code);
CREATE INDEX idx_popstats_district ON population_stats(district_lgd_code);

CREATE INDEX idx_econprofile_state ON state_economic_profile(state_code);
CREATE INDEX idx_econprofile_district ON state_economic_profile(district_lgd_code);

CREATE INDEX idx_assets_geom ON rural_assets USING GIST(geom);
CREATE INDEX idx_assets_district ON rural_assets(district_lgd_code);
CREATE INDEX idx_assets_type ON rural_assets(asset_type);

CREATE INDEX idx_roads_geom ON rural_roads USING GIST(geom);
CREATE INDEX idx_roads_district ON rural_roads(district_lgd_code);

CREATE INDEX idx_bizsummary_district ON district_business_summary(district_lgd_code);

CREATE INDEX idx_businesses_geom ON businesses USING GIST(geom);
CREATE INDEX idx_businesses_category ON businesses(category);
CREATE INDEX idx_businesses_village ON businesses(village_lgd_code);

CREATE INDEX idx_prices_district_date ON market_prices(district_lgd_code, price_date);
CREATE INDEX idx_prices_commodity ON market_prices(commodity);

CREATE INDEX idx_priceindex_state_month ON price_index(state_code, month_year);

CREATE INDEX idx_fieldobs_village ON field_observations(village_lgd_code);
CREATE INDEX idx_fieldobs_type ON field_observations(observation_type);

CREATE INDEX idx_reports_hash ON feasibility_reports(input_hash);
CREATE INDEX idx_reports_village ON feasibility_reports(village_lgd_code);
CREATE INDEX idx_reports_user ON feasibility_reports(user_id);
