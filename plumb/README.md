# Citation-Integrity / Link-Verify Engine
### An independent, modular container whose one job: cite every statement back to atomic truth — or flag it.

> Infrastructure integrity tool — **not legal advice.** Read-only over the corpus; never mutates a fact.

## The problem it solves
Statements live in `canonical_facts`, but most are **not cited back to the atomic source** — a digital twin,
a page, a 300-DPI image, and a grid location. A verbatim quote with no locator cannot be cited in a filing.
This engine measures and monitors that link integrity, and produces the **remediation queue** that says which
documents to re-scan and pin first.

## Status as of 2026-09-01 (offline snapshot, 564 facts)

| Ladder rung | meaning | n | % |
|---|---|---:|---:|
| **L4_CERTIFIABLE** | twin + page + verbatim quote | 71 | 12.6% |
| L3_LOCATED | twin + page, no quote | 2 | 0.4% |
| L2_TWIN_LINKED | twin only, no page/grid | 91 | 16.1% |
| **L1_QUOTED_FLOATING** | verbatim quote but **no** twin/page ← the defect | **354** | **62.8%** |
| L0_UNANCHORED | no quote, no anchor | 46 | 8.2% |

**Headline: only 12.6% are fully citation-anchored; 62.8% are floating verbatim quotes.** Worst single
document: the **FSOD twin** `240522_D22-03244_FSOD_001` — 12 facts, 12 floating, 0 anchored (the S069/S083
quotes we just pinned by hand are exactly this class).

## The link-integrity ladder → status vocabulary
```
L4 + image atom has a physical location (cert_guard)  -> CERTIFIED
L4 (twin+page+quote), image-location pending          -> VERIFIED
L2 / L3 (twin linked, page maybe)                     -> LINKED
L1 (quote but floating)                               -> UNCERTIFIED
L0 (no anchor)                                        -> UNVERIFIED
```

## Run
```bash
# OFFLINE (uses samples/citation_snapshot.json — runs anywhere):
python3 link_verify.py

# LIVE (per-fact, against the pg-duckdb lake / corpus):
DATABASE_URL=postgres://reader:***@pg-duckdb-lake:5432/doc_lake python3 link_verify.py

# Container + monitor (dashboard on :8091):
docker compose up -d --build
```

## What it emits
- `citation_findings.jsonl` — house linter schema: `run_id · linter · target_id · rule_id · status · severity · detail`.
  Rules: **CIT-001** floating (error) · **CIT-002** unanchored (error) · **CIT-003** twin-no-page (warn) ·
  **CIT-004** anchored (info/pass) · **CIT-005** CERTIFIED-without-image-location (cert_guard, error, live).
- `dashboard_data.json` — the monitor's data.
- `dashboard.html` — the live monitor (ladder funnel, status vocabulary, remediation queue, ↻ re-run).

## How it closes the loop (the design)
1. **Re-scan** a source document → 300-DPI images + digital twin (existing pipeline; not this engine's job).
2. **Match** each `canonical_facts.source_quote` to the twin's `page_text` (byte/fuzzy) → resolve `twin_udid`,
   `page_number`, `line_start/end`, and the **grid address** (existing grid system).
3. **Verify** the link: quote byte-matches at the located page → **VERIFIED**; image atom has a physical
   location (`image_location`) → **CERTIFIED** (enforced by the lake's `cert_guard` trigger).
4. **Monitor**: this engine re-runs the ladder, writes findings, and the dashboard shows movement L1→L4 over time.

It is deliberately **separate** from the extraction pipeline and the certification schema — one container, one
job, its own dashboard — so it can run on a schedule and never blocks or mutates the corpus.

## Relationship to the existing linters
Plugs into the same findings model as `infra/linters/lint_*.py` (parquet/images/json-twins/index-cards) and the
`SPEC_Party_Linter_Statement_Linter_Attribution_Engine.md` (its **S4 source-anchor check** is this engine's
core). This engine is the **statement→image citation** specialist; the party linter is the **speaker→party**
specialist. Together they gate a statement before it is quoted in a filing.
