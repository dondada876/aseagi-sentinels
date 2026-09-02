# Corroboration Gap Sentinel
### Delta + gap analysis, then hunt for the missing document. "Is there a file that substantiates this event — and if not, where do we go get it?"

> Infrastructure integrity tool — **not legal advice.** Read-only on the corpus *claim*; writes only
> **proposed** gaps / corroboration candidates / evidence-requests to its own tables. Never mutates a fact.
> Dummy-test-first. Candidate → confirmed foundation is a separate, human-authorized step.

## The three engines, in order
| Engine | Question | Verb |
|---|---|---|
| Citation-Integrity **Monitor** | how many statements are cited to atomic truth? | **measure** |
| Re-Anchoring **Engine** | where does this statement live in the *scanned* source? | **match** |
| Gap **Sentinel** (this) | does a document even *substantiate* this event — and if not, where is it? | **hunt** |

## What it does (three passes)
**1 · DELTA** — classify every claim by its substantiation profile:
`SUBSTANTIATED` (official source, or quote + corroboration link) · `THIN` (weak support) ·
`OPEN_GAP` (unverified, no official source, no link) · `CONTRADICTED` (a delta — opposing evidence exists).

**2 · HUNT** — for each `OPEN_GAP`/`THIN` claim, build a **search directive** (parties + date-window +
keywords) and cross-reference the **communication corpora** (WhatsApp/SMS/email/hearing turns) for candidate
corroborators — *deeper* evidence than what is already linked. Scored on **party overlap + date proximity +
keyword overlap**, with a **nexus gate**: the right parties alone never corroborate — a temporal or topical
link is required.

**3 · DIRECT** — when nothing corroborates, emit an **evidence-request directive**: the record sought, the
`target_agency`, the `event_date`, the `parties`, and the **mechanism** to actually get it (CPRA now ·
subpoena / FRCP 45 at discovery · W&I 827 for juvenile · HIPAA/H&S 123110 for medical · FRCP 34 vs the County).

## Live gap census (564 facts, read-only)
`288` have an official source · `161` carry a flagged contradiction/delta · `305` have a corroboration link ·
**`104` OPEN GAPS** (unverified, no source, no link) — the sentinel's work queue.

## Proven run
`tests/dummy_sentinel_test.py` → **ALL PASS** (delta, directive, cross-reference near event date, off-window
noise excluded via the nexus gate, agency routing). Over **5 real 2024 gaps × the 185-message WhatsApp corpus**:
all 5 found candidate corroboration (**24 candidates**) — e.g. the "missed exchange 8/6 ≠ abduction" gap
surfaced a **same-day** (2024-08-06) message from the custody-exchange thread (score 0.74), corroborating that
an exchange relationship existed. When a gap's window has no comm hit, the DIRECT pass emits the
subpoena/CPRA/827 directive instead.

## Run
```bash
python3 tests/dummy_sentinel_test.py                                   # dummy-test-first
FACTS_JSON=gaps.json COMM_GLOB='*whatsapp*.json' python3 sentinel.py   # offline
CORPUS_DSN=postgres://reader:***@lake:5432/doc_lake COMM_GLOB='/data/comms/*.json' python3 sentinel.py  # live
docker compose up --build                                             # container (dummy test, then a pass)
```

## Outputs (house schema + `schema.sql` tables)
- `evidence_gap` — the delta verdict per claim.
- `corroboration_candidate` — proposed foundations found in the comms (status `PROPOSED_FOUNDATION`).
- `evidence_request` — the go-get-it directives for gaps with no corroborator.
- `sentinel_findings.jsonl` — `run_id · linter=gap-sentinel · target_id · rule_id=GS-<verdict> · status · severity · detail`.

## Where it plugs in
- Feeds the **WDB pre-frame registry**: a pre-frame whose anchor is an `OPEN_GAP` is flagged as thin foundation
  until the sentinel finds (or the directive obtains) corroboration.
- Consumes the same **party registry** as the statement/party linter (alias → canonical party).
- Its `UNRESOLVED` cousin in the re-anchor engine (quote not in any scan) and its `OPEN_GAP` here (event with no
  document) are the two halves of "what's missing" — one says *scan it*, the other says *go get it*.
