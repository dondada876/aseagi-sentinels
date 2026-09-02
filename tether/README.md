# Statement Re-Anchoring & Authentication Engine
### An agnostic, independent container that matches every extracted statement back to its scanned source of truth — page, line, and grid — and authenticates the link.

> Infrastructure integrity tool — **not legal advice.** Read-only on the corpus *claim*; writes only
> **proposed** anchors to its own table (`statement_anchor`). It never mutates a fact or overwrites the
> corpus. Dummy-test-first (synthetic) before real records.

## How it differs from the citation-integrity monitor
| | Citation-Integrity **Monitor** | Re-Anchoring **Engine** (this) |
|---|---|---|
| Job | *measure* link integrity (the ladder) | *do the work* — match, locate, grid, authenticate, anchor |
| Writes | nothing (diagnostic) | **proposed anchors** (additive, non-destructive) |
| Output | dashboard / status | `statement_anchor` records + findings |
The monitor tells you **62.8% of statements are floating**; this engine is what **moves them down to the atom**.

## The pipeline (per statement)
```
 quote ─▶ 1. MATCH ───▶ 2. LOCATE ─────▶ 3. GRID ───────▶ 4. AUTHENTICATE ─▶ 5. ANCHOR
          exact/          twin_udid +      grid cell +       verifier-≠-        write proposed
          normalized/     page + line +    normalized bbox   extractor;         anchor (never
          fuzzy           char-span        (twinkit grid)    confidence + status mutate the fact)
```

**1 · Match** (`matcher.py`) — EXACT substring → NORMALIZED (smart-quote/whitespace/OCR fold) → FUZZY
(rapidfuzz if present, else difflib) over quote-sized windows. All candidates scored so ambiguity is visible.

**2 · Locate** — the *logical* anchor: `twin_udid + page + char_start/end`. Available **now** from the
committed `*.items.parquet` (line text). This alone lifts a statement off "floating."

**3 · Grid** — the *spatial* anchor: reuses the canonical **`twinkit/grid.py`** (semantic bands A–E ×
template columns) to compute a **grid address** (e.g. `C2`) + intersecting set + coverage + normalized bbox —
but only when the matched item carries a **pixel bbox**. Twins without coordinates return `PENDING_BBOX`
(honest: they need a coordinate-bearing re-scan). Two-tier by design.

**4 · Authenticate** — verifier-independent (the matcher proposes; an image/Vision confirm is the second
lane). Status ladder:
`RESOLVED_EXACT` (≥0.98) · `PROPOSED_FUZZY` (0.85–0.98, needs confirm) · `AMBIGUOUS` (≥2 close cross-doc
candidates → human review) · `UNRESOLVED` (<0.85 → the quote is **not in any scanned document**, i.e. the
source was never scanned or the quote was mis-transcribed).

**5 · Anchor** — writes to `statement_anchor` (`schema.sql`), **additive and idempotent**
(unique on `fact_id,twin_udid,page,char_start`). A **separate, authorized promotion step** copies
`RESOLVED_EXACT + GRID_SET` anchors into `statement_certification`, where the lake's `cert_guard` trigger
enforces the physical-image-location rule → `CERTIFIED`.

## Agnostic / independent
No case-specific logic. Point it at any corpus and any twin store:
```bash
# Dummy test first (synthetic, no real data):
python3 tests/dummy_reanchor_test.py          # -> ALL PASS

# Offline over already-scanned twins:
STATEMENTS_JSON=stmts.json TWIN_GLOB='twins/**/*.items.parquet' python3 reanchor.py

# LIVE against the lake:
CORPUS_DSN=postgres://reader:***@pg-duckdb-lake:5432/doc_lake TWIN_GLOB='/data/twins/**/*.items.parquet' python3 reanchor.py

# Container:
docker compose up --build            # runs the dummy test, then one pass
```

## Proven run (this repo, read-only)
`tests/dummy_reanchor_test.py` → **ALL PASS** (match/normalize/grid/auth/anchor). Over the 3 committed twins:
3 demo statements → **2 RESOLVED_EXACT** (located to `twin_udid + page + char-span`), **1 UNRESOLVED**
(absent), **GRID: 2 PENDING_BBOX** (committed twins carry text, not coordinates — the flag is correct).

## Outputs (house schema)
- `statement_anchors.jsonl` — proposed anchors (see `schema.sql` for the table).
- `reanchor_findings.jsonl` — `run_id · linter=reanchor · target_id · rule_id=RA-<status> · status · severity · detail`.
- `reanchor_report.json` — run tally (auth ladder, grid tiers, anchors written).

## To reach 100% anchored (the closed loop)
1. Run this engine → everything that matches an already-scanned twin gets a **logical** anchor immediately.
2. For `PENDING_BBOX`: re-run those twins through the coordinate-bearing extractor (Docling/Tesseract with
   bbox) so the **grid** anchor resolves → `GRID_SET`.
3. For `UNRESOLVED`: the source was never scanned — queue it for scanning, then re-run.
4. Promote `RESOLVED_EXACT + GRID_SET` into `statement_certification` (authorized step) → `CERTIFIED`.
5. The **citation-integrity monitor** shows the ladder moving L1→L4 as this engine works.
