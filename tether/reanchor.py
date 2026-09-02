#!/usr/bin/env python3
"""
STATEMENT RE-ANCHORING & AUTHENTICATION ENGINE  (agnostic, independent, containerized)
=====================================================================================
Distinct from the citation-integrity MONITOR (which only measures). This engine does the
WORK: for every extracted statement it (1) MATCHES the verbatim quote to the already-scanned
source text, (2) LOCATES it (twin -> page -> line/char-span, and grid cell + normalized bbox
when the twin carries coordinates), (3) AUTHENTICATES the match (verifier-independent), and
(4) writes a NON-DESTRUCTIVE re-anchor record. It never mutates a fact's claim and never
overwrites the corpus — it proposes anchors into its own table; an authorized promotion step
copies verified anchors into statement_certification.

Agnostic by design: point it at ANY corpus (STATEMENTS_JSON or CORPUS_DSN) and ANY twin store
(TWIN_GLOB). No case-specific logic. Runs offline on the committed twins, or LIVE against the lake.

    python3 reanchor.py                      # uses env / defaults, writes anchors + findings
    STATEMENTS_JSON=... TWIN_GLOB=...         # agnostic inputs
    python3 tests/dummy_reanchor_test.py      # dummy-test-first (synthetic, no real data)

Not legal advice — an infrastructure integrity tool.
"""
from __future__ import annotations
import os, sys, json, glob, hashlib, datetime, pathlib

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
import matcher, grid  # noqa: E402

# ---- authentication ladder ----
#  RESOLVED_EXACT  score>=0.98 exact/normalized substring     -> anchor VERIFIED-capable
#  PROPOSED_FUZZY  0.85<=score<0.98                            -> needs a human/vision confirm
#  AMBIGUOUS       >=2 candidates within DELTA of the top      -> HUMAN_REVIEW
#  UNRESOLVED      best<0.85 (or no hit)                       -> quote not in scanned corpus
DELTA = 0.03
FINDINGS = HERE / "reanchor_findings.jsonl"
ANCHORS = HERE / "statement_anchors.jsonl"
REPORT = HERE / "reanchor_report.json"


def auth_status(hits):
    if not hits:
        return "UNRESOLVED", None
    top = hits[0]
    if len(hits) >= 2 and (top["score"] - hits[1]["score"]) < DELTA and top["score"] < 0.98 \
            and hits[1]["twin_udid"] != top["twin_udid"]:
        return "AMBIGUOUS", top
    if top["score"] >= 0.98:
        return "RESOLVED_EXACT", top
    if top["score"] >= 0.85:
        return "PROPOSED_FUZZY", top
    return "UNRESOLVED", None


def grid_for(hit):
    """Spatial anchor when the matched item carries a pixel bbox; else PENDING_BBOX (needs re-scan)."""
    bbox = hit.get("bbox"); w = hit.get("width_px"); h = hit.get("height_px")
    if not (bbox and w and h):
        return {"grid_status": "PENDING_BBOX", "grid_address": None, "bbox_norm": None}
    tpl = grid.pick_template(hit.get("doc_type"))
    primary, inter, cov = grid.address(bbox, tpl, w, h)
    return {"grid_status": "GRID_SET", "grid_address": primary, "grid_intersecting": inter,
            "grid_coverage": cov, "bbox_norm": grid.normalize(bbox, w, h), "grid_template": tpl}


def load_statements():
    p = os.environ.get("STATEMENTS_JSON")
    if p:
        return json.loads(pathlib.Path(p).read_text())
    if os.environ.get("CORPUS_DSN"):
        import psycopg2, psycopg2.extras
        cx = psycopg2.connect(os.environ["CORPUS_DSN"])
        cur = cx.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("select fact_id as id, source_quote as quote, source_doc, category "
                    "from canonical_facts where source_quote is not null and length(source_quote)>0")
        rows = [dict(r) for r in cur.fetchall()]; cx.close()
        return rows
    return []


def load_twin_pages():
    """Load already-scanned twin text as [{twin_udid,page,ord,text,bbox?,width_px?,height_px?,doc_type?}].
    Reads *.items.parquet (line text; bbox only if the column exists) via duckdb."""
    import duckdb
    con = duckdb.connect()
    pages = []
    for f in glob.glob(os.environ.get("TWIN_GLOB", "twins/**/*.items.parquet"), recursive=True):
        try:
            cols = [c[0] for c in con.execute(f"describe select * from '{f}'").fetchall()]
            has_bbox = "bbox" in cols
            idc = "udid" if "udid" in cols else ("id" if "id" in cols else None)
            sel = con.execute(f"select * from '{f}'").fetchdf().to_dict("records")
            # group line-items into page text
            by_page = {}
            for r in sel:
                pg = r.get("page", 1)
                by_page.setdefault(pg, []).append(r)
            udid = pathlib.Path(f).stem.replace(".items", "")
            for pg, items in by_page.items():
                text = "\n".join(str(i.get("item_text", "")) for i in items)
                pages.append({"twin_udid": udid, "page": pg, "text": text,
                              "bbox": (items[0].get("bbox") if has_bbox else None)})
        except Exception:
            continue
    return pages


def run():
    run_id = "ra_" + hashlib.sha1(datetime.datetime.utcnow().isoformat().encode()).hexdigest()[:10]
    stmts = load_statements()
    pages = load_twin_pages()
    findings, anchors = [], []
    tally = {"RESOLVED_EXACT": 0, "PROPOSED_FUZZY": 0, "AMBIGUOUS": 0, "UNRESOLVED": 0}
    grid_tally = {"GRID_SET": 0, "PENDING_BBOX": 0}

    for s in stmts:
        hits = matcher.search_corpus(s.get("quote", ""), pages)
        st, top = auth_status(hits)
        tally[st] += 1
        sev = {"RESOLVED_EXACT": "info", "PROPOSED_FUZZY": "warn",
               "AMBIGUOUS": "warn", "UNRESOLVED": "error"}[st]
        detail = {"status": st, "candidates": len(hits)}
        if top:
            g = grid_for(top)
            grid_tally[g["grid_status"]] += 1
            anchor = {"run_id": run_id, "fact_id": s["id"], "twin_udid": top["twin_udid"],
                      "page": top["page"], "char_start": top["char_start"], "char_end": top["char_end"],
                      "match_method": top["method"], "match_score": top["score"],
                      "auth_status": st, "verifier": "reanchor/matcher", **g}
            anchors.append(anchor)
            detail.update({"twin_udid": top["twin_udid"], "page": top["page"],
                           "score": top["score"], "grid": g["grid_status"], "grid_address": g["grid_address"]})
        findings.append({"run_id": run_id, "linter": "reanchor", "target_id": s["id"],
                         "rule_id": f"RA-{st}", "status": "pass" if st == "RESOLVED_EXACT" else "fail",
                         "severity": sev, "detail": json.dumps(detail)})

    with FINDINGS.open("w") as fh:
        for f in findings:
            fh.write(json.dumps(f) + "\n")
    with ANCHORS.open("w") as fh:
        for a in anchors:
            fh.write(json.dumps(a) + "\n")
    report = {"run_id": run_id, "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
              "statements": len(stmts), "twin_pages": len(pages),
              "auth": tally, "grid": grid_tally, "anchors_written": len(anchors)}
    REPORT.write_text(json.dumps(report, indent=2))

    print(f"\n  RE-ANCHOR ENGINE — run {run_id}")
    print(f"  statements={len(stmts)}  twin_pages={len(pages)}")
    print("  AUTH:  " + "  ".join(f"{k}={v}" for k, v in tally.items()))
    print("  GRID:  " + "  ".join(f"{k}={v}" for k, v in grid_tally.items()))
    print(f"  anchors -> {ANCHORS.name} ({len(anchors)})  findings -> {FINDINGS.name}\n")
    return report


if __name__ == "__main__":
    run()
