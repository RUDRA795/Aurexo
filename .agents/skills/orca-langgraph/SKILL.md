# ORCA LangGraph Skill

## Purpose
Build and modify ORCA's multi-agent graph while preserving deterministic domain ownership.

## Architecture
- Graph orchestration belongs to LangGraph.
- Agent state is defined by typed ORCA schemas.
- Nodes should be small, deterministic where possible, and observable.
- Tools are registered through the ORCA tool registry rather than ad-hoc invocation.

## Core Rules
1. LLMs orchestrate and interpret; deterministic services calculate.
2. Spatial truth belongs to PostGIS/geospatial services.
3. External source selection belongs to source/arbitration logic.
4. Safety policy belongs to deterministic safety modules.
5. Every externally sourced result should retain provenance.
6. Streaming events must remain ordered and reconnectable.

## Node Pattern
- Read typed state.
- Validate required inputs.
- Invoke tools/services.
- Record evidence/provenance.
- Emit typed state/event updates.
- Avoid hidden global state.

## Tool Pattern
- Explicit input schema.
- Explicit output schema.
- Timeouts.
- Error classification.
- Source/provenance metadata.
- No direct trust in model-produced URLs or coordinates.

## Persistence
- Use the existing run persistence/event journal mechanisms.
- Do not create parallel state stores unless architecture documentation is updated.

## Verification
- Add focused tests for node transitions and tool invocation.
- Test retry/failover paths.
- Verify streaming behavior when modifying runtime execution.
