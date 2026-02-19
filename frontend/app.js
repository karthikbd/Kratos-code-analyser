let currentResult = null;      // FileAnalysis or RepoAnalysis
let currentFileIndex = 0;      // for repo view

function $(id) { return document.getElementById(id); }

function setLoading(on) {
  const overlay = $("loading-overlay");
  overlay.style.display = on ? "flex" : "none";
}

function showSection(name) {
  document.querySelectorAll(".page-section").forEach(sec => {
    sec.classList.toggle("active", sec.id === `section-${name}`);
  });
  document.querySelectorAll(".nav-item").forEach(a => {
    a.classList.toggle("active", a.dataset.section === name);
  });
}

document.querySelectorAll(".nav-item").forEach(a => {
  a.addEventListener("click", e => {
    e.preventDefault();
    showSection(a.dataset.section);
  });
});

// upload UI
const dropZone = $("drop-zone");
const fileInput = $("file-input");
const browseLink = $("browse-link");

["dragenter", "dragover"].forEach(evt => {
  dropZone.addEventListener(evt, e => {
    e.preventDefault();
    dropZone.classList.add("drag-over");
  });
});
["dragleave", "drop"].forEach(evt => {
  dropZone.addEventListener(evt, e => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
  });
});
dropZone.addEventListener("drop", e => {
  const files = e.dataTransfer.files;
  if (files && files[0]) fileInput.files = files;
});
browseLink.addEventListener("click", e => {
  e.preventDefault();
  fileInput.click();
});

async function safeFetchJson(url, options) {
  const res = await fetch(url, options);
  const text = await res.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(text || "Non-JSON response from server");
  }
  if (!res.ok) {
    throw new Error(data.detail || `${res.status} ${res.statusText}`);
  }
  return data;
}

$("analyze-btn").addEventListener("click", async () => {
  const pasted = $("paste-code").value.trim();
  const file = fileInput.files[0];
  if (!pasted && !file) {
    alert("Upload a file or paste code to analyze.");
    return;
  }

  try {
    setLoading(true);
    let result;
    if (file) {
      const fd = new FormData();
      fd.append("file", file);
      result = await safeFetchJson("/api/analyze/file", { method: "POST", body: fd });
    } else {
      const payload = {
        filename: "pasted_code.py",
        source_code: pasted,
        language: "python",
      };
      result = await safeFetchJson("/api/analyze/text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    }
    currentResult = result;
    currentFileIndex = 0;
    renderFileView(result);
    showSection("summary");
  } catch (err) {
    alert(`Analysis failed:\n\n${err.message}`);
  } finally {
    setLoading(false);
  }
});

$("analyze-github-btn").addEventListener("click", async () => {
  const url = $("github-url").value.trim();
  if (!url) {
    alert("Enter a GitHub URL.");
    return;
  }
  const type = document.querySelector("input[name='gh-type']:checked").value;
  try {
    setLoading(true);
    let result;
    if (type === "file" || url.includes("/blob/")) {
      result = await safeFetchJson("/api/analyze/github/file", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      currentResult = result;
      currentFileIndex = 0;
      renderFileView(result);
    } else {
      result = await safeFetchJson("/api/analyze/github/repo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: url }),
      });
      currentResult = result;
      currentFileIndex = 0;
      renderRepoView(result);
    }
    showSection("summary");
  } catch (err) {
    alert(`GitHub analysis failed:\n\n${err.message}`);
  } finally {
    setLoading(false);
  }
});

function escapeHtml(str) {
  return (str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// ---- renderers ----

function renderFileView(file) {
  $("analysis-meta").style.display = "block";
  $("meta-file").textContent = file.filename || "--";
  $("meta-lang").textContent = file.language || "--";
  $("meta-loc").textContent = `${file.lines_of_code ?? "--"} LOC`;
  $("meta-risk").textContent = file.qualitative_risk || "--";

  $("summary-sub").textContent =
    `${file.filename} — qualitative risk: ${file.qualitative_risk}`;
  $("summary-content").innerHTML =
    `<p class="summary-text">${escapeHtml(file.summary || "")}</p>`;

  const sectionsEl = $("narrative-sections");
  sectionsEl.innerHTML = "";
  (file.narrative_sections || []).forEach(sec => {
    const div = document.createElement("div");
    div.className = "card";
    div.innerHTML = `
      <h3>${escapeHtml(sec.heading || "")}</h3>
      <p>${escapeHtml(sec.explanation || "")}</p>`;
    sectionsEl.appendChild(div);
  });

  const controlsEl = $("controls-list");
  if (!file.inline_controls || file.inline_controls.length === 0) {
    controlsEl.innerHTML = '<p class="placeholder">No inline controls detected.</p>';
  } else {
    controlsEl.innerHTML = file.inline_controls.map(c => `
      <div class="control-card">
        <div class="control-header">
          <span class="control-reg">${escapeHtml(c.regulation)} ${escapeHtml(c.section)}</span>
          <span class="control-title">${escapeHtml(c.title)}</span>
          <span class="control-conf">${escapeHtml(c.confidence)}</span>
        </div>
        <div class="control-body">
          <div>${escapeHtml(c.description)}</div>
          <pre class="code-snippet"><code>${escapeHtml(c.evidence_snippet)}</code></pre>
        </div>
      </div>
    `).join("");
  }

  const reasoningEl = $("reasoning-list");
  reasoningEl.innerHTML = "";
  (file.reasoning_trace || []).forEach(step => {
    const li = document.createElement("li");
    li.textContent = step;
    reasoningEl.appendChild(li);
  });
}

function renderRepoView(repo) {
  $("analysis-meta").style.display = "block";
  $("meta-file").textContent = repo.repo || "--";
  $("meta-lang").textContent = "multi-file";
  $("meta-loc").textContent = `${repo.total_loc ?? "--"} LOC`;
  $("meta-risk").textContent = repo.qualitative_risk || "--";

  $("summary-sub").textContent = repo.overall_summary || "";
  $("summary-content").innerHTML = "";

  const fileSelectCard = document.createElement("div");
  fileSelectCard.className = "card";
  const options = repo.per_file
    .map((f, idx) => `<option value="${idx}">${escapeHtml(f.filename)} (${escapeHtml(f.qualitative_risk)})</option>`)
    .join("");
  fileSelectCard.innerHTML = `
    <h3>Files analyzed</h3>
    <select id="file-select">${options}</select>
    <p class="small">Select a file to view its inline controls and reasoning.</p>
  `;
  $("summary-content").appendChild(fileSelectCard);

  const first = repo.per_file[0];
  $("narrative-sections").innerHTML = "";
  renderFileView(first);

  $("file-select").addEventListener("change", e => {
    const idx = parseInt(e.target.value, 10);
    const f = repo.per_file[idx];
    renderFileView(f);
  });
}
