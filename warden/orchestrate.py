#!/usr/bin/env python3
"""
EVIDENCE-INTEGRITY ORCHESTRATOR  —  measure -> match -> hunt, one combined board.
=================================================================================
Runs the three integrity engines in sequence and rolls their reports into a single
evidence-integrity board + a merged findings stream. Each engine stays independent and
non-destructive; the orchestrator only reads their reports and aggregates.

  LANE 1  MEASURE  citation-integrity  -> link-integrity ladder (how much is anchored?)
  LANE 2  MATCH    reanchor            -> statement -> scanned source (twin+page+grid)
  LANE 3  HUNT     gap-sentinel        -> delta/gap + corroboration + evidence-requests

Shared config is passed to every engine (CORPUS_DSN / TWIN_GLOB / COMM_GLOB), so switching
the whole stack from OFFLINE (committed snapshots) to LIVE (the .91 lake) is one env change.

    python3 orchestrate.py                 # runs all three, writes combined_board.json
    docker compose up --build              # the full stack on the .91 droplet

Deploy target: 137.184.1.91 (.91).  DO NOT deploy to 104.248.69.86 (.86) — DEPRECATED.
Not legal advice — an infrastructure integrity tool.
"""
from __future__ import annotations
import os, sys, json, subprocess, hashlib, datetime, pathlib

INFRA = pathlib.Path(__file__).resolve().parent.parent           # .../infra
ROOT = INFRA.parent                                              # repo root
OUT = pathlib.Path(__file__).parent
BOARD = OUT / "combined_board.json"
FINDINGS = OUT / "combined_findings.jsonl"

# name, cwd, entrypoint, per-engine env, report file, findings file
ENGINES = [
    {"lane": "MEASURE", "name": "plumb",
     "cwd": INFRA / "plumb", "entry": "link_verify.py",
     "report": "dashboard_data.json", "findings": "citation_findings.jsonl", "env": {}},
    {"lane": "MATCH", "name": "tether",
     "cwd": INFRA / "tether", "entry": "reanchor.py",
     "report": "reanchor_report.json", "findings": "reanchor_findings.jsonl",
     "env": {"TWIN_GLOB": os.environ.get("TWIN_GLOB", str(ROOT / "twins/**/*.items.parquet")),
             "STATEMENTS_JSON": os.environ.get("STATEMENTS_JSON", str(INFRA / "tether/samples/statements.sample.json"))}},
    {"lane": "HUNT", "name": "dowser",
     "cwd": INFRA / "dowser", "entry": "sentinel.py",
     "report": "sentinel_report.json", "findings": "sentinel_findings.jsonl",
     "env": {"FACTS_JSON": os.environ.get("FACTS_JSON", str(INFRA / "dowser/samples/gap_facts.sample.json")),
             "COMM_GLOB": os.environ.get("COMM_GLOB", str(INFRA / "dowser/samples/comm.sample.json"))}},
]

SHARED = {k: os.environ[k] for k in ("CORPUS_DSN", "DATABASE_URL") if os.environ.get(k)}


def run_engine(e):
    env = {**os.environ, **SHARED, **{k: v for k, v in e["env"].items() if v}}
    try:
        subprocess.run([sys.executable, e["entry"]], cwd=str(e["cwd"]), env=env,
                       check=False, capture_output=True, timeout=600)
    except Exception as ex:
        return {"error": f"{type(ex).__name__}: {ex}"}
    rp = e["cwd"] / e["report"]
    return json.loads(rp.read_text()) if rp.exists() else {"error": "no report produced"}


def collect_findings(run_id):
    merged = []
    for e in ENGINES:
        fp = e["cwd"] / e["findings"]
        if fp.exists():
            for line in fp.read_text().splitlines():
                try:
                    merged.append({"orch_run": run_id, "lane": e["lane"], **json.loads(line)})
                except Exception:
                    pass
    with FINDINGS.open("w") as fh:
        for m in merged:
            fh.write(json.dumps(m) + "\n")
    return len(merged)


def pct(n, d):
    return round(100.0 * n / d, 1) if d else 0.0


def build_board(reports, run_id, findings_n):
    measure, match, hunt = reports["plumb"], reports["tether"], reports["dowser"]

    # LANE 1 — measure health = fully-anchored share
    ladder = {r["code"]: r["n"] for r in measure.get("ladder", [])}
    m_total = measure.get("totals", {}).get("facts", 0)
    anchored = ladder.get("L4_CERTIFIABLE", 0)
    floating = ladder.get("L1_QUOTED_FLOATING", 0)
    measure_health = pct(anchored, m_total)

    # LANE 2 — match health = resolved-exact share of statements it saw
    auth = match.get("auth", {})
    m2_total = match.get("statements", 0)
    resolved = auth.get("RESOLVED_EXACT", 0)
    match_health = pct(resolved, m2_total)
    pending_bbox = match.get("grid", {}).get("PENDING_BBOX", 0)

    # LANE 3 — hunt health = 1 - open-gap share; plus the action queue
    delta = hunt.get("delta", {})
    h_total = hunt.get("facts", 0)
    open_gaps = delta.get("OPEN_GAP", 0)
    hunt_health = pct(h_total - open_gaps, h_total)
    ev_requests = hunt.get("evidence_requests", 0)
    corroborated = hunt.get("gaps_corroborated", 0)

    overall = round((measure_health + match_health + hunt_health) / 3, 1)

    return {
        "orch_run": run_id, "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "deploy_target": os.environ.get("DROPLET_HOST", "137.184.1.91"),
        "mode": measure.get("mode", "OFFLINE"),
        "overall_integrity": overall,
        "lanes": {
            "MEASURE": {"engine": "PLUMB", "health": measure_health,
                        "facts": m_total, "anchored": anchored, "floating": floating, "ladder": ladder},
            "MATCH": {"engine": "TETHER", "health": match_health, "statements": m2_total,
                      "resolved_exact": resolved, "pending_bbox": pending_bbox, "auth": auth},
            "HUNT": {"engine": "DOWSER", "health": hunt_health, "facts": h_total,
                     "open_gaps": open_gaps, "corroborated": corroborated,
                     "evidence_requests": ev_requests, "delta": delta},
        },
        "action_queue": {
            "floating_need_anchor": floating,
            "pending_bbox_need_rescan": pending_bbox,
            "open_gaps_need_evidence": open_gaps,
            "evidence_requests_to_serve": ev_requests,
        },
        "merged_findings": findings_n,
    }


def main():
    run_id = "orch_" + hashlib.sha1(datetime.datetime.utcnow().isoformat().encode()).hexdigest()[:10]
    reports = {}
    print(f"\n  EVIDENCE-INTEGRITY ORCHESTRATOR — {run_id}")
    for e in ENGINES:
        print(f"  [{e['lane']:<7}] running {e['name']} …", flush=True)
        reports[e["name"]] = run_engine(e)
    findings_n = collect_findings(run_id)
    board = build_board(reports, run_id, findings_n)
    BOARD.write_text(json.dumps(board, indent=2))

    q = board["action_queue"]
    print("  " + "-" * 64)
    print(f"  OVERALL EVIDENCE INTEGRITY: {board['overall_integrity']}%   (mode {board['mode']}, deploy {board['deploy_target']})")
    for lane, d in board["lanes"].items():
        print(f"    {lane:<8} {d['engine']:<20} health {d['health']:>5}%")
    print("  ACTION QUEUE:")
    print(f"    floating -> anchor:        {q['floating_need_anchor']}")
    print(f"    pending-bbox -> re-scan:   {q['pending_bbox_need_rescan']}")
    print(f"    open gaps -> evidence:     {q['open_gaps_need_evidence']}")
    print(f"    evidence-requests to serve:{q['evidence_requests_to_serve']}")
    print(f"  merged findings -> {FINDINGS.name} ({findings_n}) · board -> {BOARD.name}\n")
    return board


if __name__ == "__main__":
    main()
