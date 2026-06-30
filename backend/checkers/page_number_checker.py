"""
Page number checker — PDF only.

Step 1  Brute-force 10×20 grid scan on first 5 content pages to find
        the cell where a standalone 1-3 digit number appears most often.
Step 2  Extract the page number from that cell on every content page.
Step 3  Check the collected sequence for duplicates and gaps.

"Not detected" = FAIL, not pass.
"""

import re
import base64
from collections import Counter
import fitz

# ── Constants ────────────────────────────────────────────────────────────────

GRID_COLS = 10
GRID_ROWS = 20
SCAN_PAGES = 5          # how many content pages to use for region detection
MIN_HITS   = 2          # minimum appearances to trust a cell as the page-number region

# Matches standalone 1-3 digit numbers, including zero-padded (02, 027)
_NUM_RE = re.compile(r'^(0*[1-9]\d{0,2})$')


# ── Helpers ──────────────────────────────────────────────────────────────────

def _cell_rect(page, col, row):
    r = page.rect
    cw = r.width  / GRID_COLS
    ch = r.height / GRID_ROWS
    return fitz.Rect(col * cw, row * ch, (col + 1) * cw, (row + 1) * ch)


def _read_cell(page, col, row):
    """Return (raw_str, int_val) if the cell contains a standalone number, else (None, None)."""
    rect = _cell_rect(page, col, row)
    text = page.get_text("text", clip=rect).strip()
    m = _NUM_RE.match(text)
    if m:
        return text, int(m.group(1).lstrip('0') or '0')
    return None, None


def _is_section_opener(page):
    """Full-bleed image pages have almost no extractable text — skip silently."""
    return len(page.get_text("text").strip()) < 40


def _pad_width(raw):
    """Return zero-pad width ('02' → 2) or 0 if not padded."""
    return len(raw) if raw and len(raw) > 1 and raw[0] == '0' else 0


def _fmt(n, pad):
    return str(n).zfill(pad) if pad else str(n)


def _describe_cell(col, row):
    """Map grid position to a human-readable region name."""
    h = "left"   if col < 3 else ("right" if col >= 7 else "center")
    v = "top"    if row < GRID_ROWS // 2 else "bottom"
    return f"{v}-{h} (grid {col},{row})"


# ── Step 1: grid scan ────────────────────────────────────────────────────────

def _detect_cell(doc, content_indices):
    """
    Scan first SCAN_PAGES non-opener content pages.
    Returns ((col, row), hit_count) for the winning cell, or (None, 0).
    """
    hits = Counter()
    scanned = 0

    for idx in content_indices:
        if scanned >= SCAN_PAGES:
            break
        page = doc[idx]
        if _is_section_opener(page):
            continue

        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                _, val = _read_cell(page, col, row)
                if val is not None:
                    hits[(col, row)] += 1
        scanned += 1

    if not hits:
        return None, 0

    best = max(hits, key=hits.get)
    return best, hits[best]


# ── Step 3 thumbnail ─────────────────────────────────────────────────────────

def _render_preview(page, col, row, width=520):
    """
    Render the band that contains the detected cell (top or bottom of page)
    at high resolution, with a red box around the exact cell.
    Returns base64 PNG or None.
    """
    r  = page.rect
    pw, ph = r.width, r.height
    scale = width / pw
    mat   = fitz.Matrix(scale, scale)

    # Show ~top 12% or ~bottom 12% depending on which half the cell lives in
    if row < GRID_ROWS // 2:
        clip = fitz.Rect(0, 0, pw, ph * 0.12)
    else:
        clip = fitz.Rect(0, ph * 0.88, pw, ph)

    cell_rect = _cell_rect(page, col, row)
    annot = None
    try:
        annot = page.add_rect_annot(cell_rect.inflate(2))
        annot.set_colors(stroke=(0.85, 0.1, 0.1))
        annot.set_border(width=2)
        annot.update()
        pix = page.get_pixmap(matrix=mat, clip=clip,
                               colorspace=fitz.csRGB, annots=True)
        return base64.b64encode(pix.tobytes("png")).decode()
    except Exception:
        return None
    finally:
        if annot:
            try:
                page.delete_annot(annot)
            except Exception:
                pass


# ── Main ─────────────────────────────────────────────────────────────────────

def check_page_numbers(pdf_path):
    doc   = fitz.open(pdf_path)
    total = doc.page_count

    # Fixed structure: skip title (0), TOC (1), back cover (last)
    content_indices = list(range(2, total - 1))

    # ── Step 1: find which grid cell consistently holds the page number ──────
    best_cell, confidence = _detect_cell(doc, content_indices)

    if not best_cell or confidence < MIN_HITS:
        doc.close()
        return {
            "passed":          False,
            "total_pages":     total,
            "content_pages":   len(content_indices),
            "region_detected": "not detected",
            "issue_count":     1,
            "rows": [{
                "status":   "error",
                "pdf_page": "—",
                "found":    "—",
                "region":   "—",
                "note":     "Could not detect page number location — "
                            "no cell consistently held a standalone number.",
                "img":      None,
            }],
        }

    col, row      = best_cell
    region_label  = _describe_cell(col, row)

    # ── Step 2: extract number from every content page ───────────────────────
    page_data = []
    pad = 0

    for i in content_indices:
        page   = doc[i]
        opener = _is_section_opener(page)

        raw, val = None, None
        if not opener:
            raw, val = _read_cell(page, col, row)
            if val is not None and pad == 0:
                pad = _pad_width(raw)

        page_data.append({
            "index":    i,
            "pdf_page": i + 1,
            "raw":      raw,
            "val":      val,
            "opener":   opener,
        })

    # ── Step 3: sequence validation ──────────────────────────────────────────
    numbered      = [p for p in page_data if p["val"] is not None]
    unknown_count = sum(1 for p in page_data
                        if not p["opener"] and p["val"] is None)
    values        = [p["val"] for p in numbered]

    rows      = []
    first_seen = {}

    # Duplicates
    for p in numbered:
        n = p["val"]
        if n in first_seen:
            img = _render_preview(doc[p["index"]], col, row)
            rows.append({
                "status":   "duplicate",
                "pdf_page": p["pdf_page"],
                "found":    p["raw"],
                "region":   region_label,
                "note":     f"Number {p['raw']} already used on p.{first_seen[n]}",
                "img":      img,
            })
        else:
            first_seen[n] = p["pdf_page"]

    # Gaps (subtract pages where extraction returned nothing, to suppress false positives)
    if values:
        seq_min, seq_max = min(values), max(values)
        all_gaps  = sorted(set(range(seq_min, seq_max + 1)) - set(values))
        real_gaps = all_gaps[unknown_count:]
        for n in real_gaps:
            rows.append({
                "status":   "skipped",
                "pdf_page": "—",
                "found":    "—",
                "region":   region_label,
                "note":     f"Page number {_fmt(n, pad)} is missing from the sequence",
                "img":      None,
            })

    doc.close()

    return {
        "passed":          len(rows) == 0,
        "total_pages":     total,
        "content_pages":   len(content_indices),
        "region_detected": region_label,
        "confidence":      f"{confidence}/{min(SCAN_PAGES, len(content_indices))} pages",
        "issue_count":     len(rows),
        "rows":            rows,
    }
