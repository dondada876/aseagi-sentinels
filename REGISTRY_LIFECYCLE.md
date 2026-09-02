# PROJ344 Sentinel Registry — Lifecycle
### verify · check-on-update · deprecate — how the registry stays true over time

> The registry (`registry.json`) is the single source of truth for the sentinel stack. It is
> **machine-checked** (`registry_check.py`) and **gated** (`verify_stack.sh`) so it can't drift from
> the code. Not legal advice — infrastructure.

## The three lifecycle actions

**1 · VERIFY (every merge, every deploy).**
`bash verify_stack.sh` must pass. It runs `registry_check.py` (registry ↔ filesystem) **and** every
sentinel's own verify (`plumb`, `tether`, `dowser`, `warden`). A red gate blocks the merge/deploy.

**2 · CHECK ON UPDATE (every sentinel change).**
When a sentinel changes:
1. bump its `version` in `registry.json`,
2. update any changed `entry` / `port` / `mode` / `container`,
3. re-run `bash verify_stack.sh`,
4. commit registry + code together.
`registry_check.py` fails the build if a listed dir/entry is missing, a version or verify command is
absent, a status is invalid, or a `bundles` reference is unknown — so the registry can't silently rot.

**3 · DEPRECATE (retire over time).**
To retire a sentinel or a deploy host:
1. set `status: "deprecated"` (or add a `deprecations[]` entry for a host/resource),
2. record `deprecated_on`, `replaced_by`, and a `remove_after` date (grace period),
3. keep it running through the grace period; `registry_check.py` prints a WARN,
4. after `remove_after`, the check flags it **OVERDUE** — then remove the code and the entry.

## Status values
`active` (in service) · `experimental` (present, not yet trusted for deploy) · `deprecated` (retiring).

## Deprecation ledger (live)
| Item | Deprecated | Replaced by | Remove after | Status |
|------|-----------|-------------|--------------|--------|
| `host:104.248.69.86` (.86 droplet) | 2026-09-01 | `137.184.1.91` (.91) | 2026-12-01 | deprecated |

*(The ledger lives in `registry.json → deprecations[]`; this table mirrors it for humans.)*

## Adding a new sentinel
1. create its dir + entry + a dummy test,
2. add an entry to `registry.json.sentinels[]` (id/name/role/dir/entry/container/port/mode/status/version/verify),
3. if WARDEN should run it, add its id to `warden.bundles[]` **and** wire it into `warden/orchestrate.py`,
4. `bash verify_stack.sh` → green, then commit.
