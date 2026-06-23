import re
import difflib
from docx import Document
import fitz


def extract_word_headings(docx_path):
    doc = Document(docx_path)
    headings = []
    for para in doc.paragraphs:
        style = para.style.name
        if style.startswith("Heading"):
            m = re.search(r'\d+', style)
            level = int(m.group()) if m else 1
            text = para.text.strip()
            if text:
                headings.append({"level": level, "text": text})
    return headings


def extract_pdf_toc(pdf_path):
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()
    doc.close()
    return [{"level": e[0], "text": e[1].strip(), "page": e[2]} for e in toc]


def normalize_heading(text):
    return re.sub(r'\s+', ' ', text).strip().lower()


def check_toc(docx_path, pdf_path):
    word_headings = extract_word_headings(docx_path)
    pdf_toc = extract_pdf_toc(pdf_path)

    if not pdf_toc:
        return {
            "passed": False,
            "word_heading_count": len(word_headings),
            "pdf_toc_count": 0,
            "matched_count": 0,
            "rows": [{"status": "error", "word_level": None, "word_heading": None,
                       "pdf_entry": None, "pdf_page": None,
                       "note": "PDF has no bookmarks/outline — TOC is entirely missing"}],
        }

    pdf_norms = [normalize_heading(t["text"]) for t in pdf_toc]
    word_norms = [normalize_heading(h["text"]) for h in word_headings]

    rows = []
    matched_pdf = set()
    matched_count = 0

    # Match every Word heading to a PDF TOC entry
    for wh in word_headings:
        w_norm = normalize_heading(wh["text"])
        matches = difflib.get_close_matches(w_norm, pdf_norms, n=1, cutoff=0.8)
        if matches:
            idx = pdf_norms.index(matches[0])
            matched_pdf.add(idx)
            matched_count += 1
            exact = matches[0] == w_norm
            rows.append({
                "status": "match" if exact else "mismatch",
                "word_level": wh["level"],
                "word_heading": wh["text"],
                "pdf_entry": pdf_toc[idx]["text"],
                "pdf_page": pdf_toc[idx]["page"],
                "note": None if exact else f'Text differs: PDF says "{pdf_toc[idx]["text"]}"',
            })
        else:
            rows.append({
                "status": "missing",
                "word_level": wh["level"],
                "word_heading": wh["text"],
                "pdf_entry": None,
                "pdf_page": None,
                "note": "Heading not found in PDF TOC",
            })

    # PDF TOC entries with no match in Word
    for i, pt in enumerate(pdf_toc):
        if i not in matched_pdf:
            p_norm = normalize_heading(pt["text"])
            best = difflib.get_close_matches(p_norm, word_norms, n=1, cutoff=0.8)
            if not best:
                rows.append({
                    "status": "extra",
                    "word_level": pt["level"],
                    "word_heading": None,
                    "pdf_entry": pt["text"],
                    "pdf_page": pt["page"],
                    "note": "PDF TOC entry not found in Word headings",
                })

    # Sort: errors first, then missing, extra, mismatch, match
    order = {"error": 0, "missing": 1, "extra": 2, "mismatch": 3, "match": 4}
    rows.sort(key=lambda r: order.get(r["status"], 5))

    passed = all(r["status"] in ("match",) for r in rows)

    return {
        "passed": passed,
        "word_heading_count": len(word_headings),
        "pdf_toc_count": len(pdf_toc),
        "matched_count": matched_count,
        "rows": rows,
    }
