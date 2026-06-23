import re
import fitz


def scan_band(page, band_rect):
    text = page.get_text("text", clip=band_rect).strip()
    numbers = [int(n) for n in re.findall(r'\b(\d+)\b', text)]
    return text, numbers


def check_page_numbers(pdf_path):
    doc = fitz.open(pdf_path)
    total_pages = doc.page_count
    rows = []

    for i, page in enumerate(doc):
        ph = page.rect.height
        pw = page.rect.width
        header_rect = fitz.Rect(0, 0, pw, ph * 0.12)
        footer_rect = fitz.Rect(0, ph * 0.88, pw, ph)
        expected = i + 1

        located = False
        for band_name, band_rect in [("footer", footer_rect), ("header", header_rect)]:
            band_text, numbers = scan_band(page, band_rect)
            if numbers:
                located = True
                if expected in numbers:
                    rows.append({
                        "pdf_page": expected,
                        "location": band_name,
                        "expected": expected,
                        "found": expected,
                        "status": "ok",
                    })
                else:
                    rows.append({
                        "pdf_page": expected,
                        "location": band_name,
                        "expected": expected,
                        "found": numbers[0] if numbers else "—",
                        "status": "wrong",
                    })
                break

        if not located:
            rows.append({
                "pdf_page": expected,
                "location": "—",
                "expected": expected,
                "found": "—",
                "status": "none",
            })

    doc.close()

    issue_rows = [r for r in rows if r["status"] != "ok"]
    passed = not any(r["status"] == "wrong" for r in rows)

    return {
        "passed": passed,
        "total_pages": total_pages,
        "issue_count": sum(1 for r in rows if r["status"] == "wrong"),
        "rows": issue_rows[:30],
    }
