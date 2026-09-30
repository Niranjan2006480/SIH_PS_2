-- =============================================================================
-- Migration / Data Correction Record: Tirhe Village Coordinates
-- Target: Tirhe, LGD 562182, Solapur North, Solapur, Maharashtra
-- =============================================================================
--
-- Identification:
--   Village:            Tirhe
--   Village LGD Code:   562182
--   Subdistrict/Taluka: Solapur North (LGD 4247)
--   District:           Solapur (LGD 496)
--   State:              Maharashtra (Code 27)
--
-- Context & Issue:
--   The initial coordinate ingestion from the postal gazetteer
--   (IN_clean Latitude and Longitude.csv) assigned a generic fallback postal-area
--   centroid (17.792, 75.4847) shared across 269 entries in Solapur district,
--   placing Tirhe ~34.5 km northwest of its true location.
--
-- Ground-Truth Correction Source:
--   - PMGSY Habitations GIS dataset (Habitation.shp, Record #48500:
--     HAB_NAME=Tirhe, DISTRICT_ID=517, BLOCK_ID=4343, Lon=75.779243, Lat=17.659986)
--   - Corroborated by India Post Village GPS directory (Tirhe B.O: 17.660058, 75.778568)
--     and official forest-clearance survey maps (N17°39'–17°40', E75°45'–75°48').
--
-- Note:
--   The database trigger `trg_set_geom` automatically recalculates PostGIS `geom`
--   on UPDATE. This SQL records the production correction for reproducibility.
-- =============================================================================

UPDATE locations
SET
    latitude = 17.659986,
    longitude = 75.779243,
    coordinate_source = 'pmgsy_habitation_gis',
    coordinate_accuracy = 'high'
WHERE village_lgd_code = '562182';
