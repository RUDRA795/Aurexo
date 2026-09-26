# ORCA Workstation Cleanup

## Remove from the old extension list
- bradlc.vscode-tailwindcss (not used by the current ORCA frontend)
- figma.figma-vscode (requires paid seat; not required for the current code workflow)
- mhutchie.git-graph (overlaps with GitLens)
- alefragnani.project-manager (low value with the current IDE workflow)
- rangav.vscode-thunder-client (duplicates REST Client)
- Prisma.prisma (no Prisma ORM in ORCA)
- enkia.tokyo-night (theme choice; keep one theme system)
- Catppuccin.catppuccin-vsc (theme choice; keep one theme system)
- johnpapa.vscode-peacock (not required)

## Keep
Keep the remaining specialized media, WebGL, Python, frontend, Docker, database, Git, testing, and productivity extensions from `.vscode/extensions.json`.

## Add
- ms-python.python
- ms-python.vscode-pylance
- charliermarsh.ruff
- ms-toolsai.jupyter
- dbaeumer.vscode-eslint
- ms-playwright.playwright
- GitHub.vscode-pull-request-github
- redhat.vscode-yaml

## Important
This cleanup is intentionally limited to items directly identified as redundant, irrelevant, or missing in the 2026-09-22 audit. Do not add large extension bundles without a documented ORCA requirement.
