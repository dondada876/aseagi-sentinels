# Contributing to ASEAGI Sentinels
### How to add a new sentinel, add a new case profile, and keep the registry true.

> **ASEAGI Sentinels** — *Athena, Guardian of Innocents* — is the evidence-integrity division. Sentinels are
> **case-agnostic**; each case plugs in as a **case profile**. This guide is how you grow it. Not legal advice —
> infrastructure.

## Golden rules (every contribution)
1. **Non-destructive.** A sentinel reads the corpus and writes to **its own** outputs/tables — it **never**
   mutates `canonical_facts` or overwrites source data. Promotion of a proposed result into a confirmed record
   is a separate, human-authorized step.
2. **Dummy-test-first.** Every sentinel ships a `tests/dummy_<name>_test.py` on synthetic data that passes
   before it ever touches real records.
3. **The gate is law.** `bash verify_stack.sh` must say **STACK AUTHENTICATED** before any merge or deploy.
4. **Agnostic + containerized.** No case-specific logic in engine code; config comes from env
   (`CORPUS_DSN` / `TWIN_GLOB` / `COMM_GLOB`). Each sentinel has its own `Dockerfile` + `compose.yaml`.
5. **`.91` only.** Deploy target is `137.184.1.91`; `104.248.69.86` (`.86`) is deprecated and refused by guards.

## Repo layout
```
aseagi-sentinels/
  registry.json           # source of truth: sentinels[] + case_profiles[] + deprecations[]
  registry_check.py       # validates the registry against the filesystem
  verify_stack.sh         # the gate: registry_check + every sentinel's verify + WARDEN integration
  REGISTRY_LIFECYCLE.md   # verify · check-on-update · deprecate protocol
  CONTRIBUTING.md         # this doc
  plumb/ tether/ dowser/  # the sentinels (case-agnostic)
  warden/                 # orchestrator (bundles the three) + deploy_91.sh
```

---

## Add a NEW SENTINEL
A sentinel is one self-contained job (measure / match / hunt / … a new verb). Steps:

1. **Scaffold** `newname/`:
   ```
   newname/
     newname.py            # entry point: reads inputs, writes findings + a report json, prints a status line
     <helpers>.py          # engine modules (import HERE-relative, never hardcode sibling dir names)
     tests/dummy_newname_test.py   # synthetic, ALL PASS, exits non-zero on failure
     Dockerfile            # COPY the files, CMD runs dummy test then the engine
     compose.yaml          # name: proj344 ; container_name: proj344-newname
     README.md             # what it does, run modes, outputs
     schema.sql            # (if it writes DB rows) additive tables only
   ```
2. **Emit findings in the house schema** (so WARDEN + dashboards can read them):
   `{run_id, linter:"newname", target_id, rule_id, status:"pass"|"fail", severity:"info"|"warn"|"error", detail}`
   → `newname_findings.jsonl`, plus a `newname_report.json` summary. Gitignore the run outputs.
3. **Register it** — add to `registry.json → sentinels[]`:
   ```json
   { "id":"newname","name":"NEWNAME","role":"<verb>","dir":"newname","entry":"newname.py",
     "container":"proj344-newname","port":null,"mode":"batch","status":"experimental",
     "version":"0.1.0","added":"<date>","verify":"python3 newname/tests/dummy_newname_test.py",
     "summary":"<one line>" }
   ```
   Start at `status:"experimental"` until it's trusted for deploy, then `active`.
4. **(Optional) wire it into WARDEN** — if the combined board should run it:
   - add its `id` to the WARDEN entry's `bundles[]` in `registry.json`, **and**
   - add a lane to `warden/orchestrate.py` `ENGINES[]` (`lane`, `name`, `cwd`, `entry`, `report`, `findings`),
     then map its report into `build_board()`.
5. **Verify** — `bash verify_stack.sh` → **STACK AUTHENTICATED**. Commit the code **and** `registry.json` together.

---

## Add a NEW CASE PROFILE
The sentinels don't change per case — a **case profile** points them at a case's corpus. Steps:

1. Add to `registry.json → case_profiles[]`:
   ```json
   { "id":"<caseid>","case":"<docket>","status":"active","added":"<date>",
     "corpus_project":"<supabase project or dsn ref>","twin_glob":"twins/**/*.items.parquet",
     "comm_glob":"*whatsapp*messages*.json","deploy_host":"137.184.1.91","note":"<case type>" }
   ```
2. At deploy, set the sentinels' env for that profile — in `warden/compose.yaml` (or per-sentinel compose):
   `CORPUS_DSN` / `DATABASE_URL`, `TWIN_GLOB`, `COMM_GLOB` to the profile's sources.
3. **Verify** — `registry_check.py` requires ≥1 active profile; run `bash verify_stack.sh` → green.
4. Commit. Nothing in `plumb/tether/dowser/warden` should need editing to serve a new case — if it does, that's
   case-specific logic leaking into an engine: pull it back out into the profile/env.

---

## Lifecycle — keep the registry true over time
See `REGISTRY_LIFECYCLE.md`. In short:
- **VERIFY** every merge/deploy (`verify_stack.sh`).
- **CHECK ON UPDATE** — bump `version`, re-run the gate, update `registry.json` in the same commit.
- **DEPRECATE** — set `status:"deprecated"` (or a `deprecations[]` entry) with `deprecated_on` + `replaced_by` +
  `remove_after`; `registry_check.py` WARNs during the grace period and flags **OVERDUE** after, then remove it.

## The change flow (verify before it lands)
1. Branch off `main` (e.g. `feat/<sentinel-or-profile>`).
2. Build + `bash verify_stack.sh` locally → green.
3. Open a PR. CI (or a reviewer) runs `verify_stack.sh` — a red gate blocks the merge.
4. Merge → deploy from a `.91`-mesh machine: `bash warden/deploy_91.sh`.

## Deploy quick reference
```bash
bash verify_stack.sh                               # must pass first
docker compose -f warden/compose.yaml up -d --build   # whole stack, board :8090
bash warden/deploy_91.sh                            # one-shot to 137.184.1.91 (refuses .86)
```
