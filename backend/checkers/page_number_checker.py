import re
import base64
from collections import Counter
import fitz


def is_toc_page(page):
    top = page.get_text("text").strip()[:300].lower()
    if any(kw in top for kw in ["table of contents", "contents"]):
        return True
    if len(re.findall(r'\.{4,}', page.get_text("text"))) >= 4:
        return True
    return False


def extract_page_number(page, total_pages):
    """
    Return (page_number | None, band_name).

    Strategy (most → least reliable):
      1. The only numeric word in the band that is in range 1..total_pages
      2. "Page N" / "N of M" text patterns
      3. A line whose entire content is just a number
    Never falls back to 'any number in range' to avoid false positives.
    """
    r = page.rect
    ph, pw = r.height, r.width
    bands = [
        ("footer", fitz.Rect(0, ph * 0.88, pw, ph)),
        ("header", fitz.Rect(0, 0, pw, ph * 0.12)),
    ]

    for band_name, band_rect in bands:
        # Word-level scan: collect all purely-numeric tokens in range
        words = page.get_text("words", clip=band_rect)
        in_range = [int(w[4]) for w in words
                    if re.fullmatch(r'\d{1,4}', w[4]) and 1 <= int(w[4]) <= total_pages]

        if len(in_range) == 1:
            # Only one candidate in band — very likely the page number
            return in_range[0], band_name

        # Multiple candidates: look for explicit patterns
        text = page.get_text("text", clip=band_rect)
        for pat in [r'[Pp]age\s+(\d{1,4})', r'\b(\d{1,4})\s+of\s+\d+']:
            m = re.search(pat, text)
            if m:
                n = int(m.group(1))
                if 1 <= n <= total_pages:
                    return n, band_name

        # Single-number line
        for line in text.splitlines():
            line = line.strip()
            if re.fullmatch(r'\d{1,4}', line):
                n = int(line)
                if 1 <= n <= total_pages:
                    return n, band_name

    return None, "—"


def render_thumbnail(page, width=380):
    r = page.rect
    ph, pw = r.height, r.width
    scale = width / pw
    mat = fitz.Matrix(scale, scale)
    try:
        ph_pix = page.get_pixmap(matrix=mat, clip=fitz.Rect(0, 0, pw, ph * 0.15),  colorspace=fitz.csRGB)
        pf_pix = page.get_pixmap(matrix=mat, clip=fitz.Rect(0, ph * 0.85, pw, ph), colorspace=fitz.csRGB)
        w = ph_pix.width
        h = ph_pix.height + 2 + pf_pix.height
        out = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, w, h), False)
        out.copy(ph_pix, fitz.IRect(0, 0, w, ph_pix.height))
        out.set_rect(fitz.IRect(0, ph_pix.height, w, ph_pix.height + 2), (210, 210, 210))
        out.copy(pf_pix, fitz.IRect(0, ph_pix.height + 2, w, h))
        return base64.b64encode(out.tobytes("png")).decode()
    except Exception:
        try:
            pix = page.get_pixmap(matrix=mat, clip=fitz.Rect(0, ph * 0.85, pw, ph), colorspace=fitz.csRGB)
            return base64.b64encode(pix.tobytes("png")).decode()
        except Exception:
            return None


def check_page_numbers(pdf_path):
    doc   = fitz.open(pdf_path)
    total = doc.page_count
    skipped = 0
    page_data = []

    for i, page in enumerate(doc):
        if i == 0 or i == total - 1 or is_toc_page(page):
            skipped += 1
            continue
        found, location = extract_page_number(page, total)
        page_data.append({"index": i, "pdf_page": i + 1,
                           "found": found, "location": location})

    found_list   = [p["found"] for p in page_data if p["found"] is not None]
    none_count   = sum(1 for p in page_data if p["found"] is None)
    counts       = Counter(found_list)
    duplicates   = {n for n, c in counts.items() if c > 1}

    seq_min = min(found_list) if found_list else 0
    seq_max = max(found_list) if found_list else 0
    all_gaps = sorted(set(range(seq_min, seq_max + 1)) - set(found_list))

    # Only report gaps that exceed what extraction failures can explain.
    # If we have 3 gaps but 2 pages returned None, only 1 gap is definitely real.
    real_gaps = all_gaps[none_count:]   # gaps not accountable by None pages

    rows = []
    first_seen = {}

    for entry in page_data:
        n = entry["found"]
        if n is None:
            continue
        if n in duplicates:
            if n not in first_seen:
                first_seen[n] = entry["pdf_page"]
            else:
                thumb = render_thumbnail(doc[entry["index"]])
                rows.append({
                    "status":    "duplicate",
                    "pdf_page":  entry["pdf_page"],
                    "found":     n,
                    "location":  entry["location"],
                    "note":      f"Number {n} already used on p.{first_seen[n]}",
                    "thumbnail": thumb,
                })
        else:
            first_seen[n] = entry["pdf_page"]

    for n in real_gaps:
        rows.append({
            "status":    "missing",
            "pdf_page":  "—",
            "found":     "—",
            "location":  "—",
            "note":      f"Page number {n} never appears in the document",
            "thumbnail": None,
        })

    doc.close()
    return {
        "passed":        len(rows) == 0,
        "total_pages":   total,
        "skipped_pages": skipped,
        "checked_pages": len(page_data),
        "issue_count":   len(rows),
        "rows":          rows,
    }
