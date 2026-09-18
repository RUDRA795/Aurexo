# ORCA Team Workflow

## User / project owner

- Obtain and securely store API credentials.
- Run the local stack on Windows and a physical Android device.
- Inspect real INCOIS WebGIS/network responses and provide captured responses if the adapter needs implementation help.
- Approve visual/UX decisions and validate the app on hardware.

## ORCA engineering copilot

- Maintain architecture and contracts.
- Implement backend agents/tools/schemas/tests.
- Research current source/API capabilities when required.
- Implement web rendering and data visualization.
- Debug code supplied from the live repository/environment.

## Engineering tools

- GitHub: source control/PRs/issues/CI.
- Docker: reproducible infrastructure.
- PostgreSQL/PostGIS: deterministic spatial data and geometry.
- Redis: low-latency cache/session primitives.
- QGIS: geospatial validation.
- Blender: production 3D assets and GLB optimization.
- Android Studio: Android build/device/GPU profiling.
- Browser DevTools: WebGL/WebSocket/network/performance profiling.

## Non-negotiable engineering boundary

LLMs can interpret, plan, select tools and synthesize language. They cannot author deterministic distance/geometry/safety values.
