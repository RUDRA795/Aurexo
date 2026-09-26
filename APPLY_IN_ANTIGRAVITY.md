# Antigravity Execution Directive — ORCA Cleanup + Forward Plan

Apply the workstation cleanup from this bundle to the local `D:\ORCA` workspace.

Rules:
1. Back up existing `.vscode/extensions.json` before replacement.
2. Do not delete application source code.
3. Remove only extension entries explicitly listed in `WORKSTATION_CLEANUP.md`.
4. Add the missing ORCA rules/skills exactly as provided unless the existing workspace already contains a more authoritative version.
5. Inspect the existing `.agents/mcp_config.json` and preserve its currently working servers.
6. Do not invent an unsupported Antigravity hooks/plugin schema. Validate against the installed IDE documentation before adding active hooks/plugins.
7. After edits, run the existing verification commands.
8. Then inspect the two major code gaps: `backend/orca/fusion/` and maritime safety/route geofencing.
9. Do not rewrite working LangGraph, PostGIS, SSE, RAG, or WebGL code merely for stylistic cleanup.
10. Report exact files changed, commands run, tests passed/failed, and remaining blockers.

Execution order:
A. Workstation cleanup.
B. Agent rules/skills.
C. Baseline lint/type/test.
D. Data fusion implementation plan.
E. Maritime safety implementation plan.
F. Playwright E2E foundation.
G. Live verification.
H. Media capability integration design.
