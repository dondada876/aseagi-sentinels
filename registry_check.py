#!/usr/bin/env python3
"""
PROJ344 registry check — verify · check-on-update · deprecate.
Validates registry.json against the filesystem so the sentinel registry stays true over time:
  * every ACTIVE sentinel's dir + entry file exist, has a version and a verify command;
  * status is one of active|experimental|deprecated;
  * the deploy config keeps .86 deprecated and .91 active;
  * deprecations carry deprecated_on + replaced_by, and flags any past its remove_after.
Exits non-zero on any structural failure (wire it into verify_stack.sh). Works in the monorepo
(infra/) and in the standalone repo (root) — it resolves paths relative to registry.json.
"""
from __future__ import annotations
import json, sys, datetime, pathlib

HERE = pathlib.Path(__file__).resolve().parent
REG = HERE / "registry.json"
VALID_STATUS = {"active", "experimental", "deprecated"}
errs, warns = [], []


def main():
    r = json.loads(REG.read_text())
    today = datetime.date.today().isoformat()

    # deploy config
    dep = r.get("deploy", {})
    if dep.get("active") != "137.184.1.91":
        errs.append("deploy.active must be 137.184.1.91 (.91)")
    if "104.248.69.86" not in (dep.get("deprecated") or []):
        errs.append("deploy.deprecated must include 104.248.69.86 (.86)")

    print(f"ASEAGI Sentinels registry check — {REG}")
    print(f"  platform: {r.get('platform','?')}  ({r.get('division','?')})")
    print(f"  deploy: active={dep.get('active')}  deprecated={dep.get('deprecated')}")

    # case profiles — the division serves many cases; at least one active profile required
    profiles = r.get("case_profiles", [])
    if not any(p.get("status") == "active" for p in profiles):
        errs.append("case_profiles: needs at least one active profile")
    print("  case_profiles:")
    for p in profiles:
        for req in ("id", "case", "status"):
            if not p.get(req):
                errs.append(f"case_profile {p.get('id','?')}: missing {req}")
        print(f"    {p.get('id','?'):<10} {p.get('case','?'):<12} {p.get('status','?')}")

    print("  sentinels:")
    seen = set()
    for s in r.get("sentinels", []):
        sid = s.get("id", "?"); seen.add(sid)
        d = HERE / s.get("dir", "")
        entry = d / s.get("entry", "")
        status = s.get("status")
        row = f"    {s.get('name','?'):<8} {status:<12} v{s.get('version','?'):<7} {s.get('dir')}/{s.get('entry')}"
        if status not in VALID_STATUS:
            errs.append(f"{sid}: bad status {status!r}"); row += "  [BAD STATUS]"
        if not d.is_dir():
            errs.append(f"{sid}: dir missing: {s.get('dir')}"); row += "  [DIR MISSING]"
        elif not entry.is_file():
            errs.append(f"{sid}: entry missing: {s.get('dir')}/{s.get('entry')}"); row += "  [ENTRY MISSING]"
        if not s.get("version"):
            errs.append(f"{sid}: no version")
        if not s.get("verify"):
            errs.append(f"{sid}: no verify command")
        if status == "deprecated":
            warns.append(f"{sid}: DEPRECATED (replaced_by {s.get('replaced_by','?')})")
        # bundles must reference known sentinels
        for b in s.get("bundles", []) or []:
            if b not in {x.get("id") for x in r["sentinels"]}:
                errs.append(f"{sid}: bundles unknown sentinel {b!r}")
        print(row)

    # deprecation ledger
    print("  deprecations:")
    for dpr in r.get("deprecations", []):
        if not dpr.get("deprecated_on") or not dpr.get("replaced_by"):
            errs.append(f"deprecation {dpr.get('item')}: missing deprecated_on/replaced_by")
        ra = dpr.get("remove_after")
        overdue = ra and ra < today and dpr.get("status") == "deprecated"
        print(f"    {dpr.get('item')}  -> {dpr.get('replaced_by')}  remove_after={ra}"
              + ("  [OVERDUE — remove it]" if overdue else ""))
        if overdue:
            warns.append(f"{dpr.get('item')}: past remove_after {ra} — remove the code + entry")

    print("  " + "-" * 40)
    for w in warns:
        print(f"  WARN: {w}")
    if errs:
        for e in errs:
            print(f"  ERROR: {e}")
        print(f"REGISTRY CHECK FAILED — {len(errs)} error(s).")
        return 1
    print(f"REGISTRY OK — {len(seen)} sentinels, {len(warns)} warning(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
