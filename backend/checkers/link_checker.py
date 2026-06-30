"""
Link checker — compares PDF links against the Word source.

Figma export pattern: image/logo links use a transparent text overlay,
so the PDF link annotation has a valid URL but an empty/whitespace label.
These are NOT errors. Only verify the URL exists in the Word source.

Rules:
  empty label  + URL in source     → OK
  empty label  + URL NOT in source → flag url-not-in-source
  non-empty label + URL in source  + label matches  → OK
  non-empty label + URL in source  + label mismatch → flag label-mismatch
  non-empty label + URL NOT in source               → flag url-not-in-source
  non-empty label is a raw URL                      → flag bare-url-label
"""

import re
import difflib
import fitz
from docx import Document

_W  = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
_R  = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


# ── Word source extraction ────────────────────────────────────────────────────

def _extract_word_hyperlinks(docx_path):
    """
    Returns:
      url_labels : dict  { url -> [display_text, ...] }   (from body XML)
      all_urls   : set   all external URLs in the document (from rels)
    """
    doc        = Document(docx_path)
    all_urls   = set()
    url_labels = {}

    # All external rels on the main body part (catches every URL including
    # those not wrapped in a <w:hyperlink> element)
    for rel in doc.part.rels.values():
        if rel.is_external:
            all_urls.add(rel.target_ref)

    # Walk <w:hyperlink> elements to capture display text
    for hl in doc.element.body.iter(f'{{{_W}}}hyperlink'):
        rId = hl.get(f'{{{_R}}}id')
        if not rId or rId not in doc.part.rels:
            continue
        rel = doc.part.rels[rId]
        if not rel.is_external:
            continue
        url     = rel.target_ref
        texts   = [t.text for t in hl.iter(f'{{{_W}}}t') if t.text]
        display = ''.join(texts).strip()
        url_labels.setdefault(url, []).append(display)

    return url_labels, all_urls


# ── PDF link extraction ───────────────────────────────────────────────────────

def _get_label(page, link):
    """Extract visible text over a link's bounding rect."""
    words = page.get_text("words", clip=fitz.Rect(link["from"]))
    return " ".join(w[4] for w in words).strip()


def _is_bare_url(text):
    return bool(re.match(r'^https?://', text.strip(), re.IGNORECASE))


def _labels_match(pdf_label, word_labels, cutoff=0.82):
    """True if pdf_label is close to any of the Word labels."""
    if not word_labels:
        return True   # can't compare — don't flag
    pdf_norm   = pdf_label.lower().strip()
    word_norms = [w.lower().strip() for w in word_labels if w]
    return bool(difflib.get_close_matches(pdf_norm, word_norms, n=1, cutoff=cutoff))


# ── Main check ────────────────────────────────────────────────────────────────

def check_links(pdf_path, docx_path=None):
    url_labels, all_urls = ({}, set())
    if docx_path:
        url_labels, all_urls = _extract_word_hyperlinks(docx_path)

    doc            = fitz.open(pdf_path)
    rows           = []
    total_links    = 0
    image_links    = 0   # empty-label (Figma transparent overlay)
    text_links     = 0   # non-empty label
    internal_links = 0

    for page_num, page in enumerate(doc, start=1):
        for link in page.get_links():
            kind = link.get("kind")
            if kind not in (fitz.LINK_URI, fitz.LINK_GOTO, fitz.LINK_NAMED):
                continue

            total_links += 1
            label       = _get_label(page, link)
            empty_label = not label or not label.strip()

            # ── External URL links ────────────────────────────────────────────
            if kind == fitz.LINK_URI:
                uri = link.get("uri", "")

                if empty_label:
                    # Figma transparent-overlay image link
                    image_links += 1
                    if all_urls and uri not in all_urls:
                        rows.append({
                            "pdf_page":  page_num,
                            "link_type": "Image link",
                            "label":     "(transparent overlay — Figma pattern)",
                            "url":       uri[:100],
                            "status":    "url-not-in-source",
                            "note":      "URL not found anywhere in the Word source",
                        })

                else:
                    # Visible text link
                    text_links += 1

                    if _is_bare_url(label):
                        rows.append({
                            "pdf_page":  page_num,
                            "link_type": "Text link",
                            "label":     label[:80],
                            "url":       uri[:100],
                            "status":    "bare-url-label",
                            "note":      "Link label is a raw URL — should have descriptive text",
                        })

                    elif all_urls and uri not in all_urls:
                        rows.append({
                            "pdf_page":  page_num,
                            "link_type": "Text link",
                            "label":     label[:80],
                            "url":       uri[:100],
                            "status":    "url-not-in-source",
                            "note":      "URL not found in Word source",
                        })

                    elif uri in url_labels and not _labels_match(label, url_labels[uri]):
                        word_label = url_labels[uri][0] if url_labels[uri] else "?"
                        rows.append({
                            "pdf_page":  page_num,
                            "link_type": "Text link",
                            "label":     label[:80],
                            "url":       uri[:100],
                            "status":    "label-mismatch",
                            "note":      f'Source label: "{word_label[:80]}"',
                        })

            # ── Internal links (GOTO / named) ─────────────────────────────────
            else:
                internal_links += 1
                if empty_label:
                    dest = (f"p.{link.get('page', 0) + 1}"
                            if kind == fitz.LINK_GOTO
                            else link.get("name", ""))
                    rows.append({
                        "pdf_page":  page_num,
                        "link_type": "Internal",
                        "label":     "(empty)",
                        "url":       dest,
                        "status":    "empty-label",
                        "note":      "Internal link has no visible label",
                    })

    doc.close()

    return {
        "passed":          len(rows) == 0,
        "total_links":     total_links,
        "image_links":     image_links,
        "text_links":      text_links,
        "internal_links":  internal_links,
        "issue_count":     len(rows),
        "rows":            rows[:30],
    }
