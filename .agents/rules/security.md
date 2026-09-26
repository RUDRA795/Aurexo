# ORCA Security Rules

## Input / Network Boundary
- Treat every external URL, hostname, query, uploaded payload, and adapter response as untrusted.
- Route outbound HTTP through the existing SSRF protection layer.
- Do not allow arbitrary internal-network access, loopback access, link-local access, cloud metadata access, or unsafe redirects.
- Never disable SSRF checks to make a smoke test pass.

## Sanitization
- Use the existing sanitizer and geographic policy modules at trust boundaries.
- Validate coordinates, bounding boxes, identifiers, enum-like values, and payload sizes before processing.
- Preserve canonicalized values rather than trusting raw user strings downstream.

## Secrets
- Read credentials from environment/secret stores.
- Never hard-code API keys, GitHub tokens, database passwords, or bearer tokens.
- Never place secrets into logs, telemetry attributes, prompt context, client-side bundles, or committed configuration.

## Agent Safety
- Agents may plan actions but deterministic policy code must enforce security-sensitive decisions.
- Do not let model output directly execute shell commands, SQL, browser actions, or filesystem deletion without a validated tool boundary.
- Destructive operations require an explicit, auditable tool path.

## Spatial / Operational Safety
- Enforce the existing geographic policy before maritime operational actions.
- Use authoritative spatial data and deterministic PostGIS operations for distance, containment, proximity, and geofencing.
- Do not infer maritime safety status from LLM text alone.

## Data / Logging
- Do not log raw credentials, sensitive headers, or unredacted request bodies.
- Preserve provenance for externally sourced evidence.
- Fail closed when a required security check is unavailable.

## Dependency / Supply Chain
- Pin or constrain production dependencies appropriately.
- Prefer maintained packages with clear provenance.
- Review new MCP servers, extensions, CLI tools, and npm packages before adding them to the trusted workstation surface.
