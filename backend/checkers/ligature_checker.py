import fitz

LIGATURE_MAP = {
    'ﬀ': 'ff',
    'ﬁ': 'fi',
    'ﬂ': 'fl',
    'ﬃ': 'ffi',
    'ﬄ': 'ffl',
    'ﬅ': 'ſt',
    'ﬆ': 'st',
    'Ĳ': 'IJ',
    'ĳ': 'ij',
}

CONTEXT_RADIUS = 30


def extract_context(text, char):
    """Return up to CONTEXT_RADIUS chars around each occurrence of char."""
    snippets = []
    start = 0
    while True:
        idx = text.find(char, start)
        if idx == -1:
            break
        lo = max(0, idx - CONTEXT_RADIUS)
        hi = min(len(text), idx + len(char) + CONTEXT_RADIUS)
        snippet = text[lo:hi].replace('\n', ' ').strip()
        snippets.append(snippet)
        start = idx + 1
        if len(snippets) >= 3:
            break
    return snippets


def check_ligatures(pdf_path):
    doc = fitz.open(pdf_path)
    rows = []

    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text")
        for char, name in LIGATURE_MAP.items():
            if char not in text:
                continue
            count = text.count(char)
            snippets = extract_context(text, char)
            rows.append({
                "pdf_page": page_num,
                "ligature": name,
                "unicode": f"U+{ord(char):04X}",
                "count": count,
                "context": snippets,
            })

    doc.close()

    passed = len(rows) == 0
    total = sum(r["count"] for r in rows)
    types = list(dict.fromkeys(r["ligature"] for r in rows))

    return {
        "passed": passed,
        "total_ligature_count": total,
        "ligature_types_found": types,
        "rows": rows[:30],
    }
