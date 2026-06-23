import re
import fitz


def get_link_label(page, link):
    rect = fitz.Rect(link["from"])
    words = page.get_text("words", clip=rect)
    return " ".join(w[4] for w in words).strip()


def is_bare_url(text):
    return bool(re.match(r'^https?://', text.strip(), re.IGNORECASE))


def assess_label(label, uri=""):
    if not label:
        return "issue", "Empty label"
    if is_bare_url(label):
        return "issue", "Label is a raw URL"
    if len(label) < 2:
        return "issue", "Label too short"
    return "ok", ""


def check_links(pdf_path):
    doc = fitz.open(pdf_path)
    rows = []
    total_links = 0
    external_links = 0
    internal_links = 0

    for page_num, page in enumerate(doc, start=1):
        for link in page.get_links():
            total_links += 1
            kind = link.get("kind")
            uri = link.get("uri", "")
            label = get_link_label(page, link)

            if kind == fitz.LINK_URI:
                external_links += 1
                link_type = "External"
                destination = uri[:80]
            elif kind == fitz.LINK_GOTO:
                internal_links += 1
                link_type = "Internal"
                destination = f"p. {link.get('page', 0) + 1}"
            elif kind == fitz.LINK_NAMED:
                internal_links += 1
                link_type = "Named"
                destination = link.get("name", "")
            else:
                continue

            status, issue = assess_label(label, uri)
            rows.append({
                "pdf_page": page_num,
                "type": link_type,
                "label": label or "(none)",
                "destination": destination,
                "issue": issue,
                "status": status,
            })

    doc.close()

    issue_rows = [r for r in rows if r["status"] == "issue"]
    passed = len(issue_rows) == 0

    return {
        "passed": passed,
        "total_links": total_links,
        "external_links": external_links,
        "internal_links": internal_links,
        "issue_count": len(issue_rows),
        "rows": issue_rows[:30],
    }
