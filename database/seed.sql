-- Insert initial categories
INSERT INTO category_config (category_code, display_name, target_segments, relevant_commodities, required_facilities, risk_factors, competitor_categories, pricing_method)
VALUES 
('dairy', 'Dairy', '["households","tea_shops","restaurants","schools"]', '["milk","curd","ghee"]', '["milk_collection_point","veterinary_facility","road_access"]', '["feed_cost","animal_health","daily_collection","seasonality"]', '["dairy_shop","milk_vendor","cooperative_collection"]', 'local_price_plus_cost_margin'),
('grocery', 'Grocery Retail', '["households"]', '[]', '["road_access"]', '["supply_chain_km","price_volatility"]', '["grocery_store","supermarket"]', 'cost_plus'),
('tailoring', 'Tailoring', '["households"]', '[]', '[]', '["seasonality"]', '["tailor"]', 'cost_plus');

-- Seed initial data source registry entries
INSERT INTO data_source_registry (source_id, source_name, meaning, geographic_level, unit, update_frequency, limitations) VALUES
('census_pca_2011', 'Census 2011 Primary Census Abstract', 'Population and households', 'village', 'count', 'decadal', 'Data is from 2011, may require projection'),
('lgd_2026', 'Local Government Directory', 'Village, Block, District identity', 'village', 'code', 'monthly', 'Names often mis-spelled; rely on codes'),
('pmgsy_2026', 'PMGSY GIS Data', 'Rural roads, habitations, facilities', 'point', 'geometry', 'quarterly', 'Only covers PMGSY built roads and facilities'),
('udyam_2026', 'Udyam MSME Registration', 'Formal business registration counts', 'district', 'count', 'monthly', 'Does not cover informal sector'),
('agmarknet', 'AGMARKNET Daily Prices', 'Commodity prices at mandis', 'market', 'INR', 'daily', 'Wholesale only, retail requires markup'),
('hces_2023', 'HCES 2023-24', 'Household consumption expenditure', 'state', 'INR per capita', 'multi-year', 'Only state level urban/rural split available');
