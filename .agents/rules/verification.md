# ORCA Verification & Testing Protocol

All code modifications, test additions, and agent outputs must strictly classify system capabilities by their verification tier.

## 1. Verification Tiers

1. **VERIFIED (Live Infrastructure / Live Source Tested)**
   - Requires live PostgreSQL 17 + PostGIS container or active authenticated live endpoint.
   - Tested against real services with `ORCA_LIVE_SMOKE=1`.
2. **TESTED WITH MOCK / FIXTURE**
   - Unit tests running in deterministic CI with synthetic fixtures or recorded GeoJSON/NetCDF samples.
   - Skips network requests to ensure reproducible, hermetic test runs.
3. **BLOCKED**
   - When required external or container dependencies (e.g., Docker Desktop, live database) are offline.
4. **NOT IMPLEMENTED**
   - Components where architecture exists but functional code is pending (e.g., route geofencing, procedural GLSL shaders).
   - Never claim a component is operational if its implementation files are stubs.
5. **NOT VERIFIED**
   - Code that runs without error in unit mocks but has not undergone stress testing or network degradation benchmarks.

## 2. Testing Execution
- Standard CI tests are hermetic and run via:
  ```powershell
  cd backend
  pytest -v
  ```
- End-to-end frontend tests run via Playwright:
  ```powershell
  npx playwright test
  ```
