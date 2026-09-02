"""gap_sentinel.corroborate — cross-reference an evidence GAP against communication corpora.

Given a search directive {parties, date_iso, window_days, keywords}, search a message corpus
(WhatsApp/SMS/email/hearing-turns — any [{sender,recipient,text,date,thread,hash}]) and return
ranked candidate corroborators. Score = party overlap + date proximity + keyword overlap.
Deterministic, offline, no model. This is how the sentinel finds "deeper" evidence than the twin.
"""
from __future__ import annotations
import re, json, datetime, pathlib

STOP = set("the a an and or of to in on at for with without is was are were be been being this that "
           "he she they i you it we my his her their your our not no as by from into over under than "
           "shall will would could should have has had do did done says said per re cf".split())

# alias -> canonical party (keep in sync with the party registry / WDB roster)
ALIASES = {
    "mother": "M", "mariyam": "M", "rufael": "M", "petitioner": "M", "ms. rufael": "M",
    "don": "F", "bucknor": "F", "buckner": "F", "respondent": "F", "father": "F", "mr. bucknor": "F",
    "grandfather": "GF", "yonas": "GF", "grandpa": "GF", "mgf": "GF",
    "ayanna": "SIS", "sister": "SIS", "batseba": "AUNT",
    "rivera": "RIV", "katz": "KATZ", "weiss": "WEISS", "brown": "DRB",
    "child": "CH", "ashe": "CH", "minor": "CH",
}


def parties_in(text: str) -> set[str]:
    t = (text or "").lower()
    return {cid for alias, cid in ALIASES.items() if alias in t}


def keywords_of(text: str, k: int = 8) -> list[str]:
    toks = re.findall(r"[a-z0-9§.]{4,}", (text or "").lower())
    seen, out = set(), []
    for w in toks:
        w = w.strip(".")
        if w and w not in STOP and w not in seen:
            seen.add(w); out.append(w)
    return out[:k]


def _party_of(name: str) -> str | None:
    n = (name or "").lower()
    for alias, cid in ALIASES.items():
        if alias in n:
            return cid
    return None


def _days(a_iso, b_iso):
    try:
        a = datetime.date.fromisoformat(str(a_iso)[:10]); b = datetime.date.fromisoformat(str(b_iso)[:10])
        return abs((a - b).days)
    except Exception:
        return None


def load_corpus(path: str) -> list[dict]:
    raw = json.loads(pathlib.Path(path).read_text())
    rows = raw if isinstance(raw, list) else raw.get("messages", [])
    out = []
    for m in rows:
        out.append({
            "sender": m.get("sender", ""), "recipient": m.get("recipient", ""),
            "text": m.get("message_text") or m.get("text", ""),
            "date": m.get("sent_at") or m.get("date", ""),
            "thread": m.get("thread_id") or m.get("thread", ""),
            "hash": m.get("message_hash") or m.get("hash", ""),
        })
    return out


def search(directive: dict, corpus: list[dict], min_score: float = 0.30) -> list[dict]:
    """directive = {parties:set, date_iso, window_days, keywords:list}. Returns ranked candidates."""
    want_p = set(directive.get("parties") or [])
    kws = set(directive.get("keywords") or [])
    win = directive.get("window_days", 14)
    d0 = directive.get("date_iso")
    hits = []
    for m in corpus:
        mp = {p for p in (_party_of(m["sender"]), _party_of(m["recipient"])) if p}
        party_score = 1.0 if (want_p & mp) else (0.4 if not want_p else 0.0)
        dd = _days(d0, m["date"]) if d0 else None
        date_score = 0.0 if dd is None else max(0.0, 1.0 - dd / max(1, win)) if dd <= win else 0.0
        mtok = set(keywords_of(m["text"], 40))
        kw_overlap = len(kws & mtok) / len(kws) if kws else 0.0
        # NEXUS GATE: party alone never corroborates — require a temporal OR topical link.
        if date_score == 0.0 and kw_overlap == 0.0:
            continue
        score = round(0.4 * party_score + 0.3 * date_score + 0.3 * kw_overlap, 4)
        if score >= min_score:
            hits.append({**m, "score": score, "days_off": dd, "matched_parties": sorted(mp),
                         "matched_kw": sorted(kws & mtok)})
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:10]
