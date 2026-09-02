#!/usr/bin/env python3
"""Dummy test for the Gap Sentinel — synthetic data only, NO real records. Proves:
delta classification, directive build, comm cross-reference (finds corroboration near the
event date, excludes off-window noise), and the evidence-request fallback. Non-zero on failure."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import corroborate, sentinel  # noqa: E402

# corpus in the NORMALIZED shape corroborate.search consumes
COMM = [
    {"sender": "Mother", "recipient": "Don Bucknor", "text": "you can always come see your child, no problem",
     "date": "2024-08-10T09:00:00Z", "thread": "t1", "hash": "h1"},
    {"sender": "Don Bucknor", "recipient": "Mother", "text": "There is a good cause report, contact Inspector Rivera",
     "date": "2024-08-13T10:00:00Z", "thread": "t1", "hash": "h2"},
    {"sender": "Mother", "recipient": "Don Bucknor", "text": "unrelated grocery list milk eggs",
     "date": "2023-01-01T00:00:00Z", "thread": "t2", "hash": "h3"},
]
fails = []
def ck(n, c):
    print(f"  [{'PASS' if c else 'FAIL'}] {n}")
    if not c:
        fails.append(n)

# 1. delta classification
ck("official source -> SUBSTANTIATED",
   sentinel.delta_classify({"cert_class": "CERTIFIED", "source_agency": "RPD"}) == "SUBSTANTIATED")
ck("contradiction -> CONTRADICTED",
   sentinel.delta_classify({"cert_class": "QUOTED_NO_LOCATOR", "contradicts_claim": "x"}) == "CONTRADICTED")
ck("weak + no support -> OPEN_GAP",
   sentinel.delta_classify({"cert_class": "UNVERIFIED"}) == "OPEN_GAP")

# 2. directive extraction
kws = corroborate.keywords_of("Mother offered casual access to the child on Aug 10")
ck("keywords drop stopwords", "the" not in kws and "on" not in kws)
ck("keywords keep salient", any(k in kws for k in ("offered", "casual", "access", "child")))
ck("parties resolved", corroborate.parties_in("Mother texted Don about the child") >= {"M", "F"})

# 3. cross-reference finds the corroborator near the event date, excludes off-window noise
directive = {"parties": {"M", "F"}, "date_iso": "2024-08-10", "window_days": 21,
             "keywords": corroborate.keywords_of("mother offered casual access come see child")}
hits = corroborate.search(directive, COMM)
ck("corroboration found near event date", bool(hits) and hits[0]["hash"] == "h1")
ck("off-window noise excluded", all(h["hash"] != "h3" for h in hits))

# 4. evidence-request routing (DIRECT pass) picks the right agency + mechanism
ck("police event routes to CPRA/subpoena", sentinel.guess_agency("RPD officer CAD court order violation") == "police")
ck("cfs event routes to W&I 827", "827" in sentinel.MECHANISM[sentinel.guess_agency("CFS dependency detention social worker")])

# 5. loader is callable (reads the real WhatsApp export shape message_text/sent_at/message_hash)
ck("corpus loader present", callable(corroborate.load_corpus))

print(f"\n  {'ALL PASS' if not fails else str(len(fails)) + ' FAILED: ' + ', '.join(fails)}")
sys.exit(1 if fails else 0)
