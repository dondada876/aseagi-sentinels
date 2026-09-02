#!/usr/bin/env python3
"""Dummy test for the re-anchor engine — synthetic data only, NO real records (protocol:
run a dummy test before real records). Proves the full path: match (exact/normalized/fuzzy)
-> locate -> grid address (with bbox) -> authenticate -> anchor. Exits non-zero on any failure."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import matcher, grid, reanchor  # noqa: E402

PAGES = [
    {"twin_udid": "DUMMY_DECL_001", "page": 1, "doc_type": "declaration",
     "width_px": 2550, "height_px": 3300, "bbox": [300, 1500, 2200, 1560],
     "text": "SUPERIOR COURT OF THE STATE OF CALIFORNIA\n"
             "Neither parent shall remove the child from the State of California or the United States "
             "without prior written agreement with the other parent.\n"
             "I declare under penalty of perjury that the foregoing is true and correct."},
    {"twin_udid": "DUMMY_ORDER_002", "page": 2, "doc_type": "order",
     "text": "The Court finds no immediate risk of removal and sets the matter for hearing."},
]
fails = []


def ck(name, cond):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        fails.append(name)


# 1. EXACT match locates the quote on the right page
q_exact = "without prior written agreement with the other parent"
hits = matcher.search_corpus(q_exact, PAGES)
ck("exact match found", bool(hits) and hits[0]["twin_udid"] == "DUMMY_DECL_001")
ck("exact method + score", hits and hits[0]["method"] in ("EXACT", "NORMALIZED") and hits[0]["score"] >= 0.99)
ck("char span points into the page text",
   hits and PAGES[0]["text"][hits[0]["char_start"]:hits[0]["char_end"]].lower().find("prior written") >= 0
   or hits[0]["method"] == "NORMALIZED")

# 2. NORMALIZED match survives smart-quotes / whitespace noise
q_noisy = "Neither  parent  shall   remove the child"
hits2 = matcher.search_corpus(q_noisy, PAGES)
ck("normalized/fuzzy match on noisy quote", bool(hits2) and hits2[0]["score"] >= 0.85)

# 3. GRID address computed from bbox (spatial anchor)
tpl = grid.pick_template("declaration")
addr, inter, cov = grid.address(PAGES[0]["bbox"], tpl, PAGES[0]["width_px"], PAGES[0]["height_px"])
ck("grid address is a valid cell", isinstance(addr, str) and addr[0] in "ABCDE")
ck("normalized bbox in [0,1]", all(0 <= v <= 1 for v in grid.normalize(PAGES[0]["bbox"], 2550, 3300)))

# 4. AUTHENTICATION ladder: exact -> RESOLVED_EXACT
st, top = reanchor.auth_status(hits)
ck("authenticated RESOLVED_EXACT", st == "RESOLVED_EXACT" and top is not None)

# 5. UNRESOLVED when the quote is not in any scanned page
hits3 = matcher.search_corpus("this sentence exists in no scanned document whatsoever zzz", PAGES)
st3, _ = reanchor.auth_status(hits3)
ck("unresolved when absent", st3 == "UNRESOLVED")

# 6. grid_for returns GRID_SET with bbox, PENDING_BBOX without
g_set = reanchor.grid_for({**hits[0], "doc_type": "declaration",
                           "width_px": 2550, "height_px": 3300, "bbox": [300, 1500, 2200, 1560]})
g_pending = reanchor.grid_for({"twin_udid": "DUMMY_NO_COORDS", "page": 1, "doc_type": "declaration",
                               "char_start": 0, "char_end": 10})  # no bbox/width/height
ck("grid_for GRID_SET with bbox", g_set["grid_status"] == "GRID_SET" and g_set["grid_address"])
ck("grid_for PENDING_BBOX without bbox", g_pending["grid_status"] == "PENDING_BBOX")

print(f"\n  {'ALL PASS' if not fails else str(len(fails)) + ' FAILED: ' + ', '.join(fails)}")
sys.exit(1 if fails else 0)
