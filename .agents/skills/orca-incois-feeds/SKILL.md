# ORCA INCOIS Feeds Skill

## Purpose
Maintain INCOIS WFS/THREDDS/NetCDF adapters and their dynamic discovery behavior.

## Sources
- INCOIS GeoServer WFS for PFZ.
- INCOIS THREDDS catalogs for SST/chlorophyll and related datasets.
- INCOIS text advisories where applicable.

## Adapter Contract
- Implement the existing adapter base interface.
- Normalize timestamps to UTC-aware datetimes.
- Preserve the upstream source identifier and retrieval timestamp.
- Never assume a static catalog path if dynamic discovery exists.

## THREDDS
- Discover datasets through the configured catalog discovery seam.
- Validate discovered URLs through SSRF policy before fetching.
- Handle catalog rotation and unavailable datasets without crashing the entire agent.

## NetCDF
- Validate dimensions and variable presence before extraction.
- Preserve CRS/geospatial metadata.
- Normalize units explicitly where required.
- Avoid silent interpolation or resampling unless the adapter contract requires it.

## WFS
- Validate HTTP status and content type.
- Parse GeoJSON deterministically.
- Validate geometry before persistence/use.
- Preserve feature/source identifiers.

## Testing
- Maintain parser/normalization tests with fixtures.
- Add dynamic-discovery tests for catalog changes.
- Live smoke tests remain opt-in.
