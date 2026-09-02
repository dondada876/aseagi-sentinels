# ASEAGI Sentinels
**Athena, Guardian of Innocents** — the evidence-integrity sentinel division.
Case-agnostic sentinels that verify a case corpus down to atomic truth. The first case profile is
**PROJ344** (D22-03244); more case profiles plug in via `registry.json → case_profiles[]`.

## The sentinels
- **PLUMB** (measure) — is every statement cited to atomic truth? (link-integrity ladder)
- **TETHER** (match) — where does each statement live in the scanned source? (twin + page + grid)
- **DOWSER** (hunt) — does a document substantiate the event? corroborate, or generate the subpoena directive
- **WARDEN** (orchestrate) — runs all three; one combined board + action queue

## Registry & lifecycle
`registry.json` is the source of truth (sentinels + case profiles + deprecations). `registry_check.py`
keeps it true to the filesystem; `REGISTRY_LIFECYCLE.md` is the **verify · check-on-update · deprecate** protocol.

## Run
- Verify everything: `bash verify_stack.sh` (must say STACK AUTHENTICATED).
- Whole stack: `docker compose -f warden/compose.yaml up -d --build` → board `:8090`.
- Deploy to the droplet: `bash warden/deploy_91.sh` (target 137.184.1.91; refuses 104.248.69.86).
- OFFLINE → LIVE: set `CORPUS_DSN` + `TWIN_GLOB` + `COMM_GLOB` in `warden/compose.yaml`.

Non-destructive infrastructure tooling — not legal advice.
