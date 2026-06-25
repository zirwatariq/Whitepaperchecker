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
    Find the page number printed in the header or footer.
    Returns (number_or_None, band_name).
    Priority: standalone number on its own line > 'Page N' > 'N of M' > any in-range number.
    Checks footer first, then header — but both are always scanned.
    """
    r = page.rect
    ph, pw = r.height, r.width
    bands = [
        ("footer", fitz.Rect(0, ph * 0.85, pw, ph)),
        ("header", fitz.Rect(0, 0, pw, ph * 0.15)),
    ]

    def parse(text):
        # 1. Line that is purely a number
        for line in text.splitlines():
            line = line.strip()
            if re.fullmatch(r'\d{1,4}', line):
                n = int(line)
                if 1 <= n <= total_pages:
                    return n
        # 2. "Page N"
        m = re.search(r'[Pp]age\s+(\d{1,4})', text)
        if m:
            n = int(m.group(1))
            if 1 <= n <= total_pages:
                return n
        # 3. "N of M"
        m = re.search(r'\b(\d{1,4})\s+of\s+\d+', text)
        if m:
            n = int(m.group(1))
            if 1 <= n <= total_pages:
                return n
        # 4. Any number in valid range (last resort)
        for tok in re.findall(r'\b(\d{1,4})\b', text):
            n = int(tok)
            if 1 <= n <= total_pages:
                return n
        return None

    for band_name, band_rect in bands:
        text = page.get_text("text", clip=band_rect).strip()
        n = parse(text)
        if n is not None:
            return n, band_name

    return None, "—"


def render_thumbnail(page, width=380):
    """Render header + footer strips stacked into one base64 PNG."""
    r = page.rect
    ph, pw = r.height, r.width
    scale = width / pw
    mat = fitz.Matrix(scale, scale)

    try:
        ph_clip = page.get_pixmap(matrix=mat, clip=fitz.Rect(0, 0, pw, ph * 0.15), colorspace=fitz.csRGB)
        pf_clip = page.get_pixmap(matrix=mat, clip=fitz.Rect(0, ph * 0.85, pw, ph), colorspace=fitz.csRGB)
        w = ph_clip.width
        h = ph_clip.height + 2 + pf_clip.height
        combined = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, w, h), False)
        combined.copy(ph_clip, fitz.IRect(0, 0, w, ph_clip.height))
        combined.set_rect(fitz.IRect(0, ph_clip.height, w, ph_clip.height + 2), (210, 210, 210))
        combined.copy(pf_clip, fitz.IRect(0, ph_clip.height + 2, w, h))
        return base64.b64encode(combined.tobytes("png")).decode()
    except Exception:
        try:
            pix = page.get_pixmap(matrix=mat,
                                   clip=fitz.Rect(0, ph * 0.85, pw, ph),
                                   colorspace=fitz.csRGB)
            return base64.b64encode(pix.tobytes("png")).decode()
        except Exception:
            return None


def check_page_numbers(pdf_path):
    doc = fitz.open(pdf_path)
    total_pages = doc.page_count
    skipped = 0
    page_data = []   # [{pdf_page, found, location, index}]

    for i, page in enumerate(doc):
        if i == 0 or i == total_pages - 1 or is_toc_page(page):
            skipped += 1
            continue
        found, location = extract_page_number(page, total_pages)
        page_data.append({"index": i, "pdf_page": i + 1, "found": found, "location": location})

    # Sequence analysis
    found_numbers = [p["found"] for p in page_data if p["found"] is not None]
    counts = Counter(found_numbers)
    duplicates = {n for n, c in counts.items() if c > 1}

    seq_min = min(found_numbers) if found_numbers else 0
    seq_max = max(found_numbers) if found_numbers else 0
    missing_numbers = sorted(set(range(seq_min, seq_max + 1)) - set(found_numbers))

    # Build issue rows
    rows = []
    first_seen = {}   # number -> pdf_page of first occurrence

    for entry in page_data:
        found = entry["found"]
        pdf_page = entry["pdf_page"]

        if found is None:
            status = "none"
            note = "No page number detected in header or footer"
        elif found in duplicates:
            if found not in first_seen:
                first_seen[found] = pdf_page
                continue  # first occurrence is fine
            status = "duplicate"
            note = f"Number {found} already used on p.{first_seen[found]}"
        else:
            first_seen[found] = pdf_page
            continue  # ok

        thumb = render_thumbnail(doc[entry["index"]])
        rows.append({
            "pdf_page": pdf_page,
            "location": entry["location"],
            "found": found if found is not None else "—",
            "status": status,
            "note": note,
            "thumbnail": thumb,
        })

    # Append missing-number rows (no specific page to point to)
    for n in missing_numbers:
        rows.append({
            "pdf_page": "—",
            "location": "—",
            "found": "—",
            "status": "missing",
            "note": f"Page number {n} is absent from the document",
            "thumbnail": None,
        })

    doc.close()
    passed = len(rows) == 0

    return {
        "passed": passed,
        "total_pages": total_pages,
        "skipped_pages": skipped,
        "checked_pages": len(page_data),
        "issue_count": len(rows),
        "rows": rows[:30],
    }
