#!/usr/bin/env python3
"""
CITATION-INTEGRITY / LINK-VERIFY ENGINE
=======================================
An independent, modular utility whose single job is to answer, for every statement
(canonical_facts row): *is it cited back to the atomic truth?* — i.e. does it link
to a digital twin, a page, an image atom (300-DPI), and a location/grid — and to
classify the LINK INTEGRITY as one of:

    CERTIFIED  · VERIFIED · LINKED · UNCERTIFIED · UNVERIFIED

It does NOT rebuild the corpus and it does NOT mutate facts (read-only). It emits
findings in the house linter schema (run_id, linter, target_id, rule_id, status,
severity, detail) plus a dashboard_data.json the monitor reads.

Two run modes (auto-detected):
  * LIVE   — DATABASE_URL set + psycopg2 available -> per-fact classification off the
             live corpus (the droplet / pg-duckdb lake).
  * OFFLINE— else -> reproduce the aggregate ladder from samples/citation_snapshot.json
             (so the engine runs anywhere, with the last known census).

    python3 link_verify.py            # writes dashboard_data.json + prints the status board
    DATABASE_URL=postgres://... python3 link_verify.py   # live per-fact pass

Not legal advice — an infrastructure integrity tool.
"""
from __future__ import annotations
import os, sys, json, hashlib, datetime, pathlib

HERE = pathlib.Path(__file__).parent
SNAPSHOT = HERE / "samples" / "citation_snapshot.json"
OUT = HERE / "dashboard_data.json"
FINDINGS = HERE / "citation_findings.jsonl"

# ---- the link-integrity ladder -> the status vocabulary the case-brain uses ----
# L4_CERTIFIABLE : twin + page + verbatim quote all present  (chain complete)
# L3_LOCATED     : twin + page, quote missing
# L2_TWIN_LINKED : twin only, no page locator
# L1_QUOTED_FLOATING: verbatim quote but NO twin, NO page   <-- the core defect
# L0_UNANCHORED  : no quote, no twin, no page
LADDER = ["L0_UNANCHORED", "L1_QUOTED_FLOATING", "L2_TWIN_LINKED", "L3_LOCATED", "L4_CERTIFIABLE"]

# ladder -> outward status. CERTIFIED requires the image atom to have a physical
# location (cert_guard) — only decidable in LIVE mode; offline, a full chain is VERIFIED.
def status_for(rung: str, image_located: bool | None = None) -> str:
    if rung == "L4_CERTIFIABLE":
        return "CERTIFIED" if image_located else "VERIFIED"
    if rung in ("L2_TWIN_LINKED", "L3_LOCATED"):
        return "LINKED"
    if rung == "L1_QUOTED_FLOATING":
        return "UNCERTIFIED"
    return "UNVERIFIED"

RULES = {
    "CIT-001": ("error", "verbatim quote present but NO source anchor (twin+page) — floating"),
    "CIT-002": ("error", "no quote and no anchor — unverified assertion"),
    "CIT-003": ("warn",  "linked to a twin but NO page/grid locator"),
    "CIT-004": ("info",  "fully anchored (twin+page+quote) — citation chain complete"),
    "CIT-005": ("error", "CERTIFIED claimed but image atom has no known physical location (cert_guard)"),
}


def rung_of(has_twin, has_page, has_quote):
    if has_twin and has_page and has_quote:
        return "L4_CERTIFIABLE"
    if has_twin and has_page:
        return "L3_LOCATED"
    if has_twin:
        return "L2_TWIN_LINKED"
    if has_quote:
        return "L1_QUOTED_FLOATING"
    return "L0_UNANCHORED"


def rule_for(rung):
    return {"L0_UNANCHORED": "CIT-002", "L1_QUOTED_FLOATING": "CIT-001",
            "L2_TWIN_LINKED": "CIT-003", "L3_LOCATED": "CIT-003",
            "L4_CERTIFIABLE": "CIT-004"}[rung]


def run_live(run_id):
    import psycopg2, psycopg2.extras
    cx = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = cx.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""select fact_id, source_twin_udid, source_page, source_quote, cert_class
                   from canonical_facts""")
    counts = {r: 0 for r in LADDER}
    status_counts = {}
    findings = []
    for r in cur.fetchall():
        has_twin = bool(r["source_twin_udid"])
        has_page = bool((r["source_page"] or "").strip())
        has_quote = bool((r["source_quote"] or "").strip())
        rung = rung_of(has_twin, has_page, has_quote)
        counts[rung] += 1
        st = status_for(rung, image_located=None)  # image-location check = future join to image_location
        status_counts[st] = status_counts.get(st, 0) + 1
        rid = rule_for(rung)
        sev, summary = RULES[rid]
        findings.append({"run_id": run_id, "linter": "citation-integrity", "target_id": r["fact_id"],
                         "rule_id": rid, "status": "pass" if rung == "L4_CERTIFIABLE" else "fail",
                         "severity": sev, "detail": f"{rung}: {summary}"})
    cx.close()
    total = sum(counts.values())
    ladder = [{"code": k, "n": counts[k], "pct": round(100.0 * counts[k] / total, 1) if total else 0} for k in LADDER]
    return {"mode": "LIVE", "totals": {"facts": total}, "ladder": ladder,
            "status_counts": status_counts, "worst_docs": []}, findings


def run_offline(run_id):
    snap = json.loads(SNAPSHOT.read_text())
    status_counts = {}
    findings = []
    for row in snap["ladder"]:
        rung, n = row["code"], row["n"]
        st = status_for(rung, image_located=None)
        status_counts[st] = status_counts.get(st, 0) + n
        rid = rule_for(rung)
        sev, summary = RULES[rid]
        findings.append({"run_id": run_id, "linter": "citation-integrity", "target_id": f"AGG:{rung}",
                         "rule_id": rid, "status": "pass" if rung == "L4_CERTIFIABLE" else "fail",
                         "severity": sev, "detail": f"{n} facts @ {rung}: {summary}"})
    out = {"mode": "OFFLINE", "totals": snap["totals"], "ladder": snap["ladder"],
           "status_counts": status_counts, "worst_docs": snap.get("worst_docs", []),
           "cert_class": snap.get("cert_class"), "coverage": snap.get("coverage")}
    return out, findings


def main():
    run_id = "cit_" + hashlib.sha1(datetime.datetime.utcnow().isoformat().encode()).hexdigest()[:10]
    live = bool(os.environ.get("DATABASE_URL"))
    try:
        import psycopg2  # noqa
    except Exception:
        live = False
    board, findings = (run_live(run_id) if live else run_offline(run_id))
    board["run_id"] = run_id
    board["generated_at"] = datetime.datetime.utcnow().isoformat() + "Z"

    OUT.write_text(json.dumps(board, indent=2))
    with FINDINGS.open("w") as fh:
        for f in findings:
            fh.write(json.dumps(f) + "\n")

    # ---- the status board (stdout) ----
    t = board["totals"]["facts"]
    print(f"\n  CITATION-INTEGRITY ENGINE — run {run_id} [{board['mode']}]  ·  {t} statements")
    print("  " + "-" * 66)
    print("  LINK-INTEGRITY LADDER")
    for r in board["ladder"]:
        bar = "#" * int(r["pct"] / 2)
        print(f"    {r['code']:<20} {r['n']:>4}  {r['pct']:>5}%  {bar}")
    print("  STATUS VOCABULARY")
    order = ["CERTIFIED", "VERIFIED", "LINKED", "UNCERTIFIED", "UNVERIFIED"]
    for s in order:
        if s in board["status_counts"]:
            print(f"    {s:<12} {board['status_counts'][s]:>4}")
    anchored = next((r["n"] for r in board["ladder"] if r["code"] == "L4_CERTIFIABLE"), 0)
    floating = next((r["n"] for r in board["ladder"] if r["code"] == "L1_QUOTED_FLOATING"), 0)
    print("  " + "-" * 66)
    print(f"  HEADLINE: {anchored}/{t} ({round(100*anchored/t,1)}%) fully citation-anchored; "
          f"{floating} floating verbatim quotes need a twin+page pin.")
    print(f"  findings -> {FINDINGS.name} ({len(findings)}) · dashboard -> {OUT.name}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
