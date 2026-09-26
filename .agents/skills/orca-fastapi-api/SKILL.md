# ORCA FastAPI API Skill

## Purpose
Build and maintain ORCA's FastAPI HTTP and SSE surface.

## Routing
- Keep routers thin.
- Use dependency injection for sessions/services.
- Keep Pydantic v2 contracts explicit.

## Errors
- Return stable API error shapes.
- Do not leak stack traces, credentials, or internal network details.
- Distinguish validation, upstream, timeout, unavailable, and internal failures.

## SSE / Streaming
- Emit typed events from the existing streaming runner.
- Preserve event IDs and reconnect semantics.
- Do not duplicate runtime execution when a client reconnects.
- Keep the event journal as the durable source for replay where architecture requires it.

## Security
- Route external URL inputs through SSRF validation.
- Apply input sanitization and geographic policy before operational calls.
- Use authentication/authorization boundaries when they exist; do not invent bypasses for development.

## Testing
- Contract-test endpoints.
- Test timeout/error paths.
- Add streaming tests for ordering, reconnect/replay, and terminal events.
