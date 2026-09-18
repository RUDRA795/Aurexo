-- ORCA production reference for nearest-PFZ radius filtering.
-- Geometry column should be stored as SRID 4326 POINT geography-compatible data.

SELECT
    id,
    pfz_id,
    sector,
    ST_Distance(
        geom::geography,
        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
    ) / 1000.0 AS distance_km
FROM pfz_points
WHERE valid_from <= :valid_at
  AND (valid_until IS NULL OR valid_until >= :valid_at)
  AND ST_DWithin(
        geom::geography,
        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
        :radius_m
      )
ORDER BY distance_km
LIMIT :limit;
