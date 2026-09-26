# ORCA Testing Skill

## Test Tiers
Preserve the repository's verification taxonomy:
- VERIFIED
- MOCKED
- BLOCKED
- NOT IMPLEMENTED
- NOT VERIFIED

## Backend
- Use pytest and pytest-asyncio.
- Keep unit tests deterministic.
- Use fixtures for external adapter responses.
- Exercise failover and error paths.
- Live tests remain explicitly gated.

## Frontend
- Use Playwright for browser-level E2E.
- Test critical command-center flows, agent execution, SSE updates, maps, and core WebGL lifecycle.
- Prefer stable selectors and accessibility roles.
- Do not rely on animation timing when a semantic readiness signal can be used.

## Regression
Every bug fix should add the smallest test that proves the bug cannot silently return.

## Verification
- Run focused tests first.
- Run the full suite after changes.
- Record failures and distinguish environment failures from product failures.
