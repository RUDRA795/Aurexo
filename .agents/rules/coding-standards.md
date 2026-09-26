# ORCA Coding Standards

## Scope
These rules apply to all agent-authored or agent-modified code in ORCA.

## Python
- Target Python 3.11+.
- Use Ruff as the formatter/linter authority.
- Prefer explicit type annotations on public functions, service boundaries, models, and agent state.
- Use async I/O for FastAPI, database, HTTP, Redis, and external data adapters.
- Use Pydantic v2 for API/data contracts; do not introduce v1-style validators.
- Use timezone-aware UTC datetimes internally and at persistence boundaries.
- Keep deterministic domain logic outside LLM prompts.
- Never put spatial calculations in LLM-generated code or reasoning.

## FastAPI
- Keep routers thin; put business logic in services/use-cases.
- Validate untrusted inputs at the API boundary.
- Preserve stable response contracts and provenance/evidence fields.
- SSE event schemas must remain backward compatible.

## LangGraph / Agents
- State must be typed and serializable.
- Nodes should have one clear responsibility.
- Tools must have explicit input/output contracts.
- Deterministic tools own numerical, spatial, safety, and source-arbitration decisions.
- Agent prompts may plan and interpret; they must not invent coordinates, measurements, source facts, or verification status.

## TypeScript / React
- Use strict TypeScript.
- Prefer typed props and discriminated unions for UI state.
- Keep side effects in hooks/services, not render functions.
- Dispose WebGL resources on unmount.
- Do not bypass API contracts with `any` unless the boundary is explicitly isolated and documented.

## Formatting / Naming
- Python: snake_case; classes PascalCase; constants UPPER_SNAKE_CASE.
- TypeScript/React: camelCase; components/types PascalCase.
- Prefer small modules and cohesive functions.
- Avoid speculative abstractions.

## Testing
- Every new backend behavior requires focused pytest coverage.
- API changes require contract tests.
- Frontend interaction changes should add or update Playwright coverage.
- Regression fixes should include a regression test.

## Git
- Keep commits focused and reversible.
- Do not commit secrets, generated credentials, local environment files, or large build artifacts.
- Update authoritative documentation when behavior or architecture changes.
