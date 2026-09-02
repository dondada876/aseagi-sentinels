"""reanchor.grid — vendored, self-contained mirror of twinkit/grid.py so the container
carries no repo dependency. Semantic row bands A-E + template columns; address() maps an
atom bbox to a primary grid cell + intersecting set + coverage; normalize() gives a
resolution-agnostic [0,1] bbox. Keep in sync with twinkit/grid.py (the canonical source)."""
from __future__ import annotations

ROW_BANDS = "ABCDE"  # A header · B caption/upper · C primary body · D lower body · E footer
TEMPLATES = {
    "legal_prose_5x4":     {"version": "1.0", "cols": 4, "bands": [0.12, 0.30, 0.66, 0.86, 1.00]},
    "caption_form_5x8":    {"version": "1.0", "cols": 8, "bands": [0.16, 0.34, 0.68, 0.86, 1.00]},
    "dense_form_8x8":      {"version": "1.0", "cols": 8, "bands": [0.10, 0.24, 0.52, 0.80, 1.00]},
    "pleading_line_aware": {"version": "1.0", "cols": 4, "bands": [0.10, 0.28, 0.66, 0.88, 1.00]},
}
_BY_TYPE = {"declaration": "legal_prose_5x4", "motion": "legal_prose_5x4", "brief": "legal_prose_5x4",
            "order": "legal_prose_5x4", "form": "caption_form_5x8", "fillable_form": "dense_form_8x8",
            "transcript": "pleading_line_aware", "report": "legal_prose_5x4"}


def pick_template(document_type: str) -> str:
    return _BY_TYPE.get((document_type or "").lower(), "legal_prose_5x4")


def _cells(template_id, w, h):
    t = TEMPLATES[template_id]; cols = t["cols"]; col_w = w / cols
    out, prev = [], 0.0
    for i, frac in enumerate(t["bands"]):
        y1 = frac * h
        for c in range(1, cols + 1):
            x0 = (c - 1) * col_w
            out.append((f"{ROW_BANDS[i]}{c}", [round(x0), round(prev), round(x0 + col_w), round(y1)]))
        prev = y1
    return out


def _overlap(a, b):
    x0 = max(a[0], b[0]); y0 = max(a[1], b[1]); x1 = min(a[2], b[2]); y1 = min(a[3], b[3])
    return max(0, x1 - x0) * max(0, y1 - y0)


def address(bbox_px, template_id, w, h):
    """(primary_address, intersecting[], coverage{}). Coverage = share of the atom's area per cell."""
    area = max(1, (bbox_px[2] - bbox_px[0]) * (bbox_px[3] - bbox_px[1]))
    cov = {}
    for addr, b in _cells(template_id, w, h):
        ov = _overlap(bbox_px, b)
        if ov > 0:
            cov[addr] = round(ov / area, 4)
    if not cov:
        return "A1", ["A1"], {"A1": 1.0}
    primary = max(cov, key=cov.get)
    return primary, sorted(cov, key=cov.get, reverse=True), cov


def normalize(bbox_px, w, h):
    return [round(bbox_px[0] / w, 4), round(bbox_px[1] / h, 4),
            round(bbox_px[2] / w, 4), round(bbox_px[3] / h, 4)]
