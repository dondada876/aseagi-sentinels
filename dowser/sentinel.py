#!/usr/bin/env python3
"""
CORROBORATION GAP SENTINEL  (delta + gap analysis, then hunt for the missing document)
=====================================================================================
The third integrity engine. The monitor MEASURES link integrity; the re-anchor engine MATCHES
statements to already-scanned sources; this SENTINEL asks the deeper question:

    For each asserted event/claim — is there a file or document that SUBSTANTIATES it?
    If not, WHERE do we go find it?

It runs three passes:
  1. DELTA    — classify every claim by its substantiation profile
                (SUBSTANTIATED · THIN · OPEN_GAP · CONTRADICTED).
  2. HUNT     — for each OPEN_GAP/THIN claim, build a search directive (parties + date-window +
                keywords) and cross-reference the COMMUNICATION corpora (WhatsApp/SMS/hearing turns)
                for candidate corroborators, deeper than what is already linked.
  3. DIRECT   — when nothing corroborates, emit an EVIDENCE-REQUEST directive: what record, which
                agency, which date, which mechanism (CPRA / subpoena / FRCP 34 / FRCP 45).

Non-destructive: writes PROPOSED corroboration candidates + gap findings to its own outputs; never
mutates a fact. Agnostic: FACTS_JSON|CORPUS_DSN + COMM_GLOB. Not legal advice.

    python3 tests/dummy_sentinel_test.py     # dummy-test-first (synthetic)
    FACTS_JSON=gaps.json COMM_GLOB='*.json' python3 sentinel.py
"""
from __future__ import annotations
import os, sys, json, glob, hashlib, datetime, pathlib

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
import corroborate  # noqa: E402

FINDINGS = HERE / "sentinel_findings.jsonl"
CANDIDATES = HERE / "corroboration_candidates.jsonl"
REQUESTS = HERE / "evidence_requests.jsonl"
REPORT = HERE / "sentinel_report.json"

# agency -> how you actually get its records (the DIRECT pass playbook)
MECHANISM = {
    "police": "CPRA now; FRCP 45 subpoena once at discovery",
    "da": "CPRA / Pitchess; FRCP 45 at discovery",
    "cfs": "CPRA; W&I 827 petition for juvenile records; FRCP 34 vs County",
    "court": "reporter's transcript request; JV-570/JV-571 for juvenile",
    "medical": "HIPAA authorization / H&S 123110; FRCP 45",
    "comms": "party's own production; FRCP 34; preservation letter",
}


def delta_classify(f: dict) -> str:
    cert = f.get("cert_class")
    has_official = bool((f.get("source_agency") or "").strip())
    has_related = bool(f.get("related_fact_ids"))
    has_quote = bool((f.get("source_quote") or f.get("quote") or "").strip())
    has_contra = bool((f.get("contradicts_claim") or "").strip())
    if has_contra:
        return "CONTRADICTED"
    if has_official or (has_quote and has_related):
        return "SUBSTANTIATED"
    if cert in ("UNVERIFIED", "ASSERTED_NO_QUOTE") and not has_official and not has_related:
        return "OPEN_GAP"
    return "THIN"


def guess_agency(text: str) -> str:
    t = (text or "").lower()
    if any(w in t for w in ("rpd", "bpd", "opd", "police", "officer", "detective", "cad", "sheriff")):
        return "police"
    if any(w in t for w in ("da ", "district attorney", "rivera", "weiss", "prosecut", "278.7", "gcr")):
        return "da"
    if any(w in t for w in ("cfs", "cps", "social worker", "dependency", "detention", "juvenile", "w&i", "wic")):
        return "cfs"
    if any(w in t for w in ("court", "hearing", "foah", "minute order", "transcript", "judge")):
        return "court"
    if any(w in t for w in ("doctor", "exam", "kaiser", "clinic", "forensic", "mychart", "diagnos")):
        return "medical"
    if any(w in t for w in ("text", "whatsapp", "email", "message", "sms", "audio")):
        return "comms"
    return "comms"


def load_facts():
    p = os.environ.get("FACTS_JSON")
    if p:
        return json.loads(pathlib.Path(p).read_text())
    if os.environ.get("CORPUS_DSN"):
        import psycopg2, psycopg2.extras
        cx = psycopg2.connect(os.environ["CORPUS_DSN"])
        cur = cx.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("select fact_id as id, claim_short, claim, to_char(fact_date,'YYYY-MM-DD') as fact_date, "
                    "source_agency, cert_class, source_quote, contradicts_claim, related_fact_ids "
                    "from canonical_facts")
        rows = [dict(r) for r in cur.fetchall()]; cx.close()
        return rows
    return []


def load_comm():
    corpus = []
    for f in glob.glob(os.environ.get("COMM_GLOB", "*whatsapp*messages*.json")):
        try:
            corpus += corroborate.load_corpus(f)
        except Exception:
            continue
    return corpus


def run():
    run_id = "sn_" + hashlib.sha1(datetime.datetime.utcnow().isoformat().encode()).hexdigest()[:10]
    facts = load_facts()
    comm = load_comm()
    findings, candidates, requests = [], [], []
    delta = {"SUBSTANTIATED": 0, "THIN": 0, "OPEN_GAP": 0, "CONTRADICTED": 0}
    corroborated = 0

    for f in facts:
        cls = delta_classify(f)
        delta[cls] += 1
        if cls not in ("OPEN_GAP", "THIN"):
            findings.append({"run_id": run_id, "linter": "gap-sentinel", "target_id": f["id"],
                             "rule_id": f"GS-{cls}", "status": "pass", "severity": "info",
                             "detail": json.dumps({"delta": cls})})
            continue
        text = f.get("claim_short") or f.get("claim") or ""
        directive = {"parties": corroborate.parties_in(text), "date_iso": f.get("fact_date"),
                     "window_days": 21, "keywords": corroborate.keywords_of(text)}
        hits = corroborate.search(directive, comm) if comm else []
        if hits:
            corroborated += 1
            for h in hits[:5]:
                candidates.append({"run_id": run_id, "fact_id": f["id"], "source": "comms",
                                   "msg_hash": h["hash"], "sender": h["sender"], "recipient": h["recipient"],
                                   "date": h["date"], "score": h["score"], "matched_kw": h["matched_kw"],
                                   "excerpt": (h["text"] or "")[:160], "status": "PROPOSED_FOUNDATION"})
            findings.append({"run_id": run_id, "linter": "gap-sentinel", "target_id": f["id"],
                             "rule_id": "GS-CORROBORATED", "status": "fail", "severity": "warn",
                             "detail": json.dumps({"delta": cls, "candidates": len(hits),
                                                   "top_score": hits[0]["score"]})})
        else:
            agency = guess_agency(text)
            req = {"run_id": run_id, "fact_id": f["id"], "event": text[:140],
                   "event_date": f.get("fact_date"), "target_agency": agency,
                   "record_sought": f"document substantiating: {text[:80]}",
                   "mechanism": MECHANISM.get(agency, MECHANISM["comms"]),
                   "parties": sorted(directive["parties"])}
            requests.append(req)
            findings.append({"run_id": run_id, "linter": "gap-sentinel", "target_id": f["id"],
                             "rule_id": "GS-OPEN_GAP-NO_CORROBORATION", "status": "fail", "severity": "error",
                             "detail": json.dumps({"delta": cls, "agency": agency})})

    for path, rows in ((FINDINGS, findings), (CANDIDATES, candidates), (REQUESTS, requests)):
        with path.open("w") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
    report = {"run_id": run_id, "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
              "facts": len(facts), "comm_messages": len(comm), "delta": delta,
              "gaps_corroborated": corroborated, "evidence_requests": len(requests),
              "candidates": len(candidates)}
    REPORT.write_text(json.dumps(report, indent=2))

    print(f"\n  GAP SENTINEL — run {run_id}   facts={len(facts)}  comm={len(comm)}")
    print("  DELTA:  " + "  ".join(f"{k}={v}" for k, v in delta.items()))
    print(f"  HUNT:   {corroborated} gaps found candidate corroboration in comms ({len(candidates)} candidates)")
    print(f"  DIRECT: {len(requests)} evidence-request directives (no corroboration found -> go get it)")
    print(f"  -> {CANDIDATES.name} · {REQUESTS.name} · {FINDINGS.name}\n")
    return report


if __name__ == "__main__":
    run()
