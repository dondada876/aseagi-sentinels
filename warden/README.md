# Evidence-Integrity Orchestrator
### Runs all three sentinel engines — measure → match → hunt — and rolls them into one board.

> Infrastructure integrity tool — **not legal advice.** Each engine stays independent and
> non-destructive; the orchestrator only reads their reports and aggregates.

## Deploy target
- **✅ 137.184.1.91 (`.91`)** — ASEAGI legal / Docling droplet. The stack runs here.
- **⛔ 104.248.69.86 (`.86`) — DEPRECATED.** Do not deploy; being retired. All compose/config point at `.91`.

## The three lanes
```
 LANE 1  MEASURE   citation-integrity   how much is cited to atomic truth?     -> link-integrity ladder
 LANE 2  MATCH     reanchor             where does it live in the scan?         -> twin+page+grid anchors
 LANE 3  HUNT      gap-sentinel         does a document substantiate the event? -> corroborate / subpoena
```
The orchestrator runs them in order, reads each engine's report, and computes an **overall evidence-integrity
score** (mean of the three lane healths) plus a single **action queue**:

| Action | Source lane | Meaning |
|---|---|---|
| floating → anchor | MEASURE (L1) | verbatim quotes with no twin/page link |
| pending-bbox → re-scan | MATCH | matched, but the twin has no coordinates for a grid anchor |
| open gaps → evidence | HUNT (OPEN_GAP) | events with no substantiating document |
| evidence-requests → serve | HUNT (DIRECT) | the CPRA/subpoena/W&I-827 directives to actually get the record |

## Run
```bash
python3 orchestrate.py                 # runs all three, writes combined_board.json + merged findings
python3 serve.py                       # + the board on :8090
docker compose up -d --build           # the full stack (context=infra/), board on :8090
```

## OFFLINE → LIVE (one env change)
Shared config is forwarded to every engine, so flipping the whole stack is a single line in `compose.yaml`:
```
CORPUS_DSN / DATABASE_URL  -> the .91 pg-duckdb lake   (facts + monitor go LIVE, per-fact)
TWIN_GLOB                  -> /data/twins/**/*.items.parquet
COMM_GLOB                  -> /data/comms/*.json        (the full ~70k-message corpus, not the 185 local)
```

## Proven run (this repo, OFFLINE)
`python3 orchestrate.py` ran all three: **MEASURE 12.6% · MATCH 66.7% · HUNT 0%** (sample gaps) → **overall
26.4%**, action queue `{floating 354, pending-bbox 2, open-gaps 3, evidence-requests 1}`, **11 merged findings**,
deploy target `137.184.1.91`. (OFFLINE health reflects sample inputs; LIVE runs the full corpus.)

## Outputs
- `combined_board.json` — the rollup the board reads.
- `combined_findings.jsonl` — all three engines' findings, tagged by `lane`, in the house schema.
- `board.html` — the combined dashboard (three lanes + overall + action queue + ↻ run all).

## How it fits the stack
It sits above `infra/plumb`, `infra/tether`, `infra/dowser` and the
`infra/pg-duckdb-lake`. Nothing here mutates the corpus; promotion of any proposed anchor or corroboration
candidate into a confirmed foundation remains a separate, human-authorized step.
