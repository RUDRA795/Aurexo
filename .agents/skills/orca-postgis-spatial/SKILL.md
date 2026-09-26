---
name: orca-postgis-spatial
description: Guides spatial queries, spherical calculations, and pgvector operations for the ORCA PostgreSQL 17 + PostGIS 3.5 database. Use when writing, modifying, or debugging database models, Alembic migrations, or spatial queries in backend/orca/database/.
---

# ORCA PostGIS & Spatial Reasoning Skill

## 1. PostGIS 17 Geography Invariants
- Always use `geography(Point, 4326)` or `geography(MultiLineString, 4326)` for maritime features.
- Compute spherical distances using `ST_Distance(geom1::geography, geom2::geography)`.
- Use `ST_DWithin(geom1::geography, geom2::geography, distance_in_meters)` for radial proximity queries.
- Index all spatial columns using GiST:
  ```sql
  CREATE INDEX idx_advisories_geom ON marine_advisories USING GIST (geom);
  ```

## 2. pgvector Advisory Embeddings
- Column type: `vector(1536)` (or model dimension).
- Indexing: HNSW index using cosine distance:
  ```sql
  CREATE INDEX idx_advisories_embedding ON marine_advisories USING hnsw (embedding vector_cosine_ops);
  ```
- Querying nearest neighbors:
  ```sql
  SELECT id, title, 1 - (embedding <=> :query_vector) AS similarity
  FROM marine_advisories
  ORDER BY embedding <=> :query_vector
  LIMIT :top_k;
  ```

## 3. Containerized Verification
- PostgreSQL runs via `docker-compose.yml` on port `5432`.
- Verify database connection and vector extension before running integration tests:
  ```powershell
  docker compose exec db psql -U orca_user -d orca_db -c "SELECT postgis_full_version();"
  ```
