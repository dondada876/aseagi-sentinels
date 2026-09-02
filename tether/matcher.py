"""reanchor.matcher — find where an extracted quote lives in the already-scanned text.

Strategy ladder (first strong hit wins, but all candidates are scored so ambiguity is visible):
  1. EXACT      — verbatim substring of a page's text.
  2. NORMALIZED — substring after whitespace/case/quote/OCR folding (â€œ->", ligatures, etc.).
  3. FUZZY      — best token-similarity over sliding windows (rapidfuzz if present, else difflib).

No network, no model. Verifier-independent: this proposes; authentication confirms against the image.
"""
from __future__ import annotations
import re, unicodedata, difflib

try:
    from rapidfuzz import fuzz as _rf
except Exception:
    _rf = None

_WS = re.compile(r"\s+")
_OCR = {"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-",
        " ": " ", "ﬁ": "fi", "ﬂ": "fl"}


def norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    for a, b in _OCR.items():
        s = s.replace(a, b)
    return _WS.sub(" ", s).strip().lower()


def _ratio(a: str, b: str) -> float:
    if _rf:
        return _rf.token_set_ratio(a, b) / 100.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def find_in_page(quote: str, page_text: str):
    """Return best {method, score, char_start, char_end} for quote within one page's text, or None."""
    if not quote or not page_text:
        return None
    q, p = quote.strip(), page_text
    # 1. exact
    i = p.find(q)
    if i >= 0:
        return {"method": "EXACT", "score": 1.0, "char_start": i, "char_end": i + len(q)}
    # 2. normalized substring
    nq, np_ = norm(q), norm(p)
    j = np_.find(nq)
    if j >= 0 and nq:
        return {"method": "NORMALIZED", "score": 0.99, "char_start": j, "char_end": j + len(nq)}
    # 3. fuzzy over windows sized to the quote
    if len(nq) < 8:
        return None
    words = np_.split(" ")
    qlen = max(1, len(nq.split(" ")))
    best = None
    step = 1 if len(words) < 400 else 2
    for k in range(0, max(1, len(words) - qlen + 1), step):
        window = " ".join(words[k:k + qlen])
        sc = _ratio(nq, window)
        if best is None or sc > best["score"]:
            cs = len(" ".join(words[:k])) + (1 if k else 0)
            best = {"method": "FUZZY", "score": round(sc, 4), "char_start": cs, "char_end": cs + len(window)}
    if best and best["score"] >= 0.72:
        return best
    return None


def search_corpus(quote: str, pages: list[dict]):
    """pages = [{twin_udid, page, ord?, text, bbox?, doc_type?}]. Returns ranked candidates."""
    hits = []
    for pg in pages:
        m = find_in_page(quote, pg.get("text", ""))
        if m:
            hits.append({**pg, **m})
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits
