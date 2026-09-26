# ORCA Next Phases After Workstation Cleanup

## Phase A — Agent Workstation
1. Apply `.vscode/extensions.json`.
2. Add the four ORCA rules/skills in `.agents/`.
3. Verify all workspace MCP servers start.
4. Validate GitHub authentication without exposing credentials.
5. Run the backend lint/type/test baseline.

## Phase B — Engineering Gaps
1. Implement `backend/orca/fusion/`.
2. Implement maritime safety / route geofencing logic.
3. Set up Playwright E2E infrastructure and critical command-center flows.
4. Reconcile the README verification claims with actual implementation.
5. Extract/share standalone GLSL only if the rendering directory is intended as a maintained artifact.

## Phase C — Live Verification
1. Start Docker Compose.
2. Verify PostgreSQL/PostGIS/pgvector.
3. Run full backend tests.
4. Run opt-in live smoke tests.
5. Run Playwright E2E.
6. Capture a verification matrix with evidence.

## Phase D — Agent Capability Expansion
Add media capabilities as external tools/services only after the core workstation is stable:
- image generation
- video generation/editing
- TTS/STT
- 3D asset generation/conversion
- media analysis
Each capability must have a bounded tool interface, timeouts, provenance, and cost/resource controls.

## Phase E — Portable ORCA Agent System
Package rules, skills, and MCP configuration into a portable `.agents/plugins/orca-agent-system/` bundle only after the Antigravity plugin schema is validated against the installed IDE version.
