const API = "http://127.0.0.1:5050/api/check";

// ── File upload wiring ──────────────────────────────────────────────────────

const wordInput    = document.getElementById("word-input");
const pdfInput     = document.getElementById("pdf-input");
const wordFilename = document.getElementById("word-filename");
const pdfFilename  = document.getElementById("pdf-filename");
const wordDrop     = document.getElementById("word-drop");
const pdfDrop      = document.getElementById("pdf-drop");
const checkBtn     = document.getElementById("check-btn");
const btnText      = document.getElementById("btn-text");
const btnSpinner   = document.getElementById("btn-spinner");
const resultsSection = document.getElementById("results");
const summaryBar   = document.getElementById("summary-bar");
const checksList   = document.getElementById("checks-list");
const errorBanner  = document.getElementById("error-banner");
const errorText    = document.getElementById("error-text");

let wordFile = null;
let pdfFile  = null;

function updateBtn() { checkBtn.disabled = !(wordFile && pdfFile); }

function setFile(type, file) {
  if (type === "word") {
    wordFile = file;
    wordFilename.textContent = file.name;
    wordDrop.classList.add("has-file");
  } else {
    pdfFile = file;
    pdfFilename.textContent = file.name;
    pdfDrop.classList.add("has-file");
  }
  updateBtn();
}

wordInput.addEventListener("change", () => { if (wordInput.files[0]) setFile("word", wordInput.files[0]); });
pdfInput.addEventListener("change",  () => { if (pdfInput.files[0])  setFile("pdf",  pdfInput.files[0]); });

function setupDrop(el, type, ext) {
  el.addEventListener("dragover", e => { e.preventDefault(); el.classList.add("dragging"); });
  el.addEventListener("dragleave", () => el.classList.remove("dragging"));
  el.addEventListener("drop", e => {
    e.preventDefault(); el.classList.remove("dragging");
    const f = e.dataTransfer.files[0];
    if (f && f.name.toLowerCase().endsWith(ext)) setFile(type, f);
  });
}
setupDrop(wordDrop, "word", ".docx");
setupDrop(pdfDrop,  "pdf",  ".pdf");

// ── HTML helpers ────────────────────────────────────────────────────────────

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function pill(status, label) {
  return `<span class="pill pill-${esc(status)}">${esc(label)}</span>`;
}

function pageRef(n) {
  return n ? `<span class="page-ref">p. ${esc(n)}</span>` : `<span style="color:var(--muted)">—</span>`;
}

function dash() { return `<span style="color:var(--muted)">—</span>`; }

// ── Table builders ──────────────────────────────────────────────────────────

function tableWrap(html) {
  return `<div class="cmp-table-wrap"><table class="cmp-table">${html}</table></div>`;
}

function buildContentTable(rows) {
  if (!rows.length) return `<p class="pass-msg">✓ No content differences found.</p>`;
  const head = `<thead><tr>
    <th>Status</th>
    <th>Word Source</th>
    <th>PDF</th>
    <th>PDF Page</th>
  </tr></thead>`;
  const body = rows.map(r => {
    const labels = { missing: "Missing from PDF", extra: "Extra in PDF", mismatch: "Text differs" };
    return `<tr class="row-${esc(r.status)}">
      <td>${pill(r.status, labels[r.status] ?? r.status)}</td>
      <td>${r.word ? esc(r.word) : dash()}</td>
      <td>${r.pdf  ? esc(r.pdf)  : dash()}</td>
      <td>${pageRef(r.pdf_page)}</td>
    </tr>`;
  }).join("");
  return tableWrap(head + `<tbody>${body}</tbody>`);
}

function buildTocTable(rows) {
  if (!rows.length) return `<p class="pass-msg">✓ All headings matched.</p>`;
  const head = `<thead><tr>
    <th>Status</th>
    <th>Level</th>
    <th>Word Heading</th>
    <th>PDF TOC Entry</th>
    <th>PDF Page</th>
  </tr></thead>`;
  const labels = { match: "Match", missing: "Missing", extra: "Extra", mismatch: "Differs", error: "Error" };
  const body = rows.map(r => `<tr class="row-${esc(r.status)}">
    <td>${pill(r.status, labels[r.status] ?? r.status)}</td>
    <td>${r.word_level ? `H${esc(r.word_level)}` : dash()}</td>
    <td>${r.word_heading ? esc(r.word_heading) : dash()}</td>
    <td>${r.pdf_entry   ? esc(r.pdf_entry)   : dash()}
        ${r.note && r.status !== "match" ? `<div class="note-cell">${esc(r.note)}</div>` : ""}</td>
    <td>${pageRef(r.pdf_page)}</td>
  </tr>`).join("");
  return tableWrap(head + `<tbody>${body}</tbody>`);
}

function buildPageTable(rows) {
  if (!rows.length) return `<p class="pass-msg">✓ All page numbers are correct.</p>`;
  const labels = { wrong: "Wrong number", none: "No number found" };
  const head = `<thead><tr>
    <th>PDF Page</th>
    <th>Location</th>
    <th>Expected</th>
    <th>Found</th>
    <th>Status</th>
  </tr></thead>`;
  const body = rows.map(r => `<tr class="row-${esc(r.status)}">
    <td>${pageRef(r.pdf_page)}</td>
    <td>${esc(r.location)}</td>
    <td>${esc(r.expected)}</td>
    <td><strong>${esc(r.found)}</strong></td>
    <td>${pill(r.status, labels[r.status] ?? r.status)}</td>
  </tr>`).join("");
  return tableWrap(head + `<tbody>${body}</tbody>`);
}

function buildLinkTable(rows) {
  if (!rows.length) return `<p class="pass-msg">✓ All links have meaningful labels.</p>`;
  const head = `<thead><tr>
    <th>PDF Page</th>
    <th>Type</th>
    <th>Label in PDF</th>
    <th>Destination</th>
    <th>Issue</th>
  </tr></thead>`;
  const body = rows.map(r => `<tr class="row-wrong">
    <td>${pageRef(r.pdf_page)}</td>
    <td>${esc(r.type)}</td>
    <td><strong>${esc(r.label)}</strong></td>
    <td style="font-size:.74rem;color:var(--muted)">${esc(r.destination)}</td>
    <td>${pill("missing", esc(r.issue))}</td>
  </tr>`).join("");
  return tableWrap(head + `<tbody>${body}</tbody>`);
}

function buildLigatureTable(rows) {
  if (!rows.length) return `<p class="pass-msg">✓ No ligature glyphs detected — ligatures are off.</p>`;
  const head = `<thead><tr>
    <th>PDF Page</th>
    <th>Ligature</th>
    <th>Unicode</th>
    <th>Count</th>
    <th>Context (turn off ligatures here)</th>
  </tr></thead>`;
  const body = rows.map(r => {
    const ctxHtml = (r.context || []).map(c =>
      `<span class="ctx-chip">${esc(c)}</span>`
    ).join(" ");
    return `<tr class="row-wrong">
      <td>${pageRef(r.pdf_page)}</td>
      <td><strong>${esc(r.ligature)}</strong></td>
      <td><code>${esc(r.unicode)}</code></td>
      <td>${esc(r.count)}</td>
      <td><div class="context-block">${ctxHtml || dash()}</div></td>
    </tr>`;
  }).join("");
  return tableWrap(head + `<tbody>${body}</tbody>`);
}

// ── Card builder ────────────────────────────────────────────────────────────

const CHECKS = [
  {
    key: "content",
    title: "Content Match",
    desc: "Text in PDF matches source Word document",
    stats: d => [
      { label: "Similarity", value: d.similarity_percent + "%" },
      { label: "Word §", value: d.word_paragraph_count },
      { label: "PDF §", value: d.pdf_paragraph_count },
    ],
    table: d => buildContentTable(d.rows || []),
  },
  {
    key: "toc",
    title: "Table of Contents",
    desc: "PDF bookmarks match headings in source",
    stats: d => [
      { label: "Word headings", value: d.word_heading_count },
      { label: "PDF TOC entries", value: d.pdf_toc_count },
      { label: "Matched", value: d.matched_count },
    ],
    table: d => buildTocTable(d.rows || []),
  },
  {
    key: "page_numbers",
    title: "Page Numbers",
    desc: "Page numbers in headers/footers are correct",
    stats: d => [
      { label: "Total pages", value: d.total_pages },
      { label: "Issues", value: d.issue_count },
    ],
    table: d => buildPageTable(d.rows || []),
  },
  {
    key: "links",
    title: "Link Labels",
    desc: "All hyperlinks have meaningful labels",
    stats: d => [
      { label: "Total links", value: d.total_links },
      { label: "External", value: d.external_links },
      { label: "Internal", value: d.internal_links },
      { label: "Issues", value: d.issue_count },
    ],
    table: d => buildLinkTable(d.rows || []),
  },
  {
    key: "ligatures",
    title: "Ligatures",
    desc: "No ligature glyphs (ﬁ ﬂ ﬀ) — must be off for Plus Jakarta Sans",
    stats: d => [
      { label: "Ligature glyphs", value: d.total_ligature_count },
      { label: "Types", value: (d.ligature_types_found || []).join(", ") || "none" },
    ],
    table: d => buildLigatureTable(d.rows || []),
  },
];

function renderCard(def, data) {
  const status = data.passed ? "pass" : "fail";
  const icon   = data.passed ? "✓" : "✗";
  const badge  = data.passed ? "Passed" : "Failed";

  const statsHtml = (def.stats(data) || []).map(s =>
    `<span class="stat-chip"><strong>${esc(s.value)}</strong> ${esc(s.label)}</span>`
  ).join("");

  const bodyHtml = data.error
    ? `<p style="color:var(--fail);font-size:.85rem">${esc(data.error)}</p>`
    : def.table(data);

  return `
    <div class="check-card ${status}" data-key="${def.key}">
      <div class="check-header" onclick="toggleCard(this)">
        <div class="check-icon ${status}">${icon}</div>
        <div class="check-meta">
          <h3>${def.title}</h3>
          <p class="check-desc">${def.desc}</p>
        </div>
        <div class="check-stats">${statsHtml}</div>
        <span class="badge ${status}">${badge}</span>
        <span class="chevron">▾</span>
      </div>
      <div class="check-body">${bodyHtml}</div>
    </div>`;
}

function toggleCard(header) {
  const card = header.closest(".check-card");
  card.classList.toggle("open");
}

// ── Submit ──────────────────────────────────────────────────────────────────

checkBtn.addEventListener("click", async () => {
  if (!wordFile || !pdfFile) return;

  resultsSection.classList.add("hidden");
  errorBanner.classList.add("hidden");
  btnText.textContent = "Checking…";
  btnSpinner.classList.remove("hidden");
  checkBtn.disabled = true;

  const form = new FormData();
  form.append("word", wordFile);
  form.append("pdf", pdfFile);

  try {
    const resp = await fetch(API, { method: "POST", body: form });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || "Server error");

    // Summary bar
    summaryBar.innerHTML = CHECKS.map(def => {
      const d = data[def.key] || {};
      const status = d.passed ? "pass" : "fail";
      const icon   = d.passed ? "✓" : "✗";
      return `<span class="summary-chip ${status}">${icon} ${def.title}</span>`;
    }).join("");

    // Cards — auto-open failed ones
    checksList.innerHTML = CHECKS.map(def => {
      const d = data[def.key] || { passed: false, error: "No data returned" };
      return renderCard(def, d);
    }).join("");

    // Open failed cards by default
    document.querySelectorAll(".check-card.fail").forEach(c => c.classList.add("open"));

    resultsSection.classList.remove("hidden");
    resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    errorText.textContent = err.message;
    errorBanner.classList.remove("hidden");
  } finally {
    btnText.textContent = "Run Checks";
    btnSpinner.classList.add("hidden");
    checkBtn.disabled = false;
  }
});
