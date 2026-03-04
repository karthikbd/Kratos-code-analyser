/* eslint-env browser */
/* ============================================================
   KRATOS  FDIC 370 Compliance Analyzer  Frontend Logic
   ============================================================ */

"use strict";

// 
// GLOBALS
// 
let gResult   = null;   // FDIC370Analysis response object
let gFindings = [];     // flat array of control findings (for table/detail)

function el(id) { return document.getElementById(id); }
function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

// 
// NAVIGATION
// 
function showSection(name) {
  document.querySelectorAll('.page-section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(a => a.classList.remove('active'));
  const sec = el('section-' + name);
  if (sec) sec.classList.add('active');
  const navBtn = document.querySelector('.nav-item[data-section="' + name + '"]');
  if (navBtn) navBtn.classList.add('active');
}

document.querySelectorAll('.nav-item').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    showSection(a.dataset.section);
  });
});

// 
// LOADING OVERLAY
// 
let stageTimer = null;
let stageIndex = 0;
const STAGES = ['stage-1', 'stage-2', 'stage-3', 'stage-4'];

function showLoading() {
  stageIndex = 0;
  STAGES.forEach(id => {
    const s = el(id);
    s.classList.remove('active', 'done');
  });
  el(STAGES[0]).classList.add('active');
  el('loading-overlay').style.display = 'flex';
  stageTimer = setInterval(() => {
    el(STAGES[stageIndex]).classList.remove('active');
    el(STAGES[stageIndex]).classList.add('done');
    stageIndex++;
    if (stageIndex < STAGES.length) {
      el(STAGES[stageIndex]).classList.add('active');
    } else {
      clearInterval(stageTimer);
    }
  }, 3500);
}

function hideLoading() {
  clearInterval(stageTimer);
  STAGES.forEach(id => {
    const s = el(id);
    s.classList.remove('active');
    s.classList.add('done');
  });
  setTimeout(() => {
    el('loading-overlay').style.display = 'none';
    STAGES.forEach(id => el(id).classList.remove('done'));
  }, 400);
}

// 
// FILE UPLOAD HANDLING
// 
el('drop-zone').addEventListener('dragover', e => { e.preventDefault(); el('drop-zone').classList.add('drag-over'); });
el('drop-zone').addEventListener('dragleave', () => el('drop-zone').classList.remove('drag-over'));
el('drop-zone').addEventListener('drop', e => {
  e.preventDefault();
  el('drop-zone').classList.remove('drag-over');
  handleFiles(e.dataTransfer.files);
});
el('drop-zone').addEventListener('click', () => el('file-input').click());
el('browse-link').addEventListener('click', e => { e.stopPropagation(); el('file-input').click(); });
el('file-input').addEventListener('change', () => handleFiles(el('file-input').files));

function handleFiles(files) {
  if (!files || files.length === 0) return;
  const list = el('files-list');
  list.innerHTML = '';
  Array.from(files).forEach(f => {
    const div = document.createElement('div');
    div.className = 'file-entry';
    div.innerHTML = '<span class="file-entry-name">' + esc(f.name) + '</span><span class="file-entry-size">' + formatBytes(f.size) + '</span>';
    list.appendChild(div);
  });
  el('selected-files').style.display = 'block';
  el('analyze-btn').style.display = 'block';
}

function formatBytes(b) {
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
  return (b / 1048576).toFixed(1) + ' MB';
}

el('analyze-btn').addEventListener('click', async () => {
  const files = el('file-input').files;
  if (!files || files.length === 0) return;
  const fd = new FormData();
  Array.from(files).forEach(f => fd.append('files', f));
  await runAnalysis('/api/analyze/fdic370/files', fd, 'multipart');
});

// 
// PASTE HANDLING
// 
el('paste-code').addEventListener('input', () => {
  const hasCode = el('paste-code').value.trim().length > 0;
  el('paste-options').style.display = hasCode ? 'flex' : 'none';
  el('analyze-paste-btn').style.display = hasCode ? 'block' : 'none';
});

el('analyze-paste-btn').addEventListener('click', async () => {
  const code = el('paste-code').value.trim();
  if (!code) return;
  const payload = {
    filename: el('paste-filename').value || 'pasted_code.py',
    source_code: code,
    language: el('paste-lang').value || 'python'
  };
  await runAnalysis('/api/analyze/fdic370/text', payload, 'json');
});

// 
// GITHUB HANDLING
// 
el('analyze-github-btn').addEventListener('click', async () => {
  const url = el('github-url').value.trim();
  if (!url) { alert('Please enter a GitHub URL.'); return; }
  const typeRadio = document.querySelector('input[name="gh-type"]:checked');
  const scanType = typeRadio ? typeRadio.value : 'file';
  const payload = { url, scan_type: scanType };
  await runAnalysis('/api/analyze/fdic370/github', payload, 'json');
});

// 
// CORE ANALYSIS RUNNER
// 
async function runAnalysis(endpoint, payload, mode) {
  showLoading();
  try {
    let resp;
    if (mode === 'multipart') {
      resp = await fetch(endpoint, { method: 'POST', body: payload });
    } else {
      resp = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    }
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || 'Analysis failed with status ' + resp.status);
    }
    gResult = await resp.json();
    gFindings = gResult.control_findings || [];
    hideLoading();
    renderAll(gResult);
    showSection('executive');
  } catch (e) {
    hideLoading();
    alert('Analysis error: ' + e.message);
  }
}

// 
// RENDER ALL SECTIONS
// 
function renderAll(data) {
  renderSidebarMeta(data);
  renderExecutiveSummary(data);
  renderCoverageStats(data);
  renderDetailedFindings(data.control_findings || []);
  renderLineage(data);
  renderRemediationPlan(data.remediation_plan);
}

// 
// SIDEBAR META
// 
function renderSidebarMeta(data) {
  el('analysis-meta').style.display = 'block';
  el('meta-files').textContent    = data.files_analyzed || '--';
  el('meta-loc').textContent      = (data.total_loc || 0).toLocaleString();
  el('meta-controls').textContent = (data.coverage_stats ? data.coverage_stats.total_controls : '--');
  const posture = data.executive_summary ? data.executive_summary.posture : '--';
  const metaP = el('meta-posture');
  metaP.textContent = posture;
  metaP.className   = 'meta-value posture-badge posture-' + posture;
  const langs = (data.languages || []);
  el('meta-languages').textContent = langs.length ? langs.map(l => l.charAt(0).toUpperCase() + l.slice(1)).join(', ') : '--';
  const durSec = data.analysis_duration_ms ? (data.analysis_duration_ms / 1000).toFixed(1) + 's' : '--';
  el('meta-duration').textContent = durSec;
}

// 
// EXECUTIVE SUMMARY
// 
function renderExecutiveSummary(data) {
  const ex = data.executive_summary || {};
  const posture = ex.posture || 'Unknown';
  const gaps    = ex.top_critical_gaps || [];
  const prios   = ex.immediate_priorities || [];

  let gapsHtml = gaps.map(g => '<li><span class="gap-bullet"></span>' + esc(g) + '</li>').join('') || '<li><span class="gap-bullet"></span>No critical gaps identified.</li>';
  let prioHtml  = prios.map(p => '<li><span class="priority-bullet"></span>' + esc(p) + '</li>').join('') || '<li><span class="priority-bullet"></span>No immediate priorities identified.</li>';

  let statsRow = '';
  const cs = data.coverage_stats;
  if (cs) {
    statsRow = '<div class="coverage-stats-grid" style="margin-bottom:16px">'
      + statCard('PASS',   cs.pass_count,    'pass-color')
      + statCard('PARTIAL',cs.partial_count, 'partial-color')
      + statCard('FAIL',   cs.fail_count,    'fail-color')
      + statCard('COMPLIANCE', cs.compliance_pct.toFixed(1) + '%', 'total-color')
      + '</div>';
  }

  const durBadge = data.analysis_duration_ms
    ? `<span class="exec-duration-badge">&#9201;&nbsp;${(data.analysis_duration_ms/1000).toFixed(1)}s analysis</span>`
    : '';
  const langBadge = (data.languages || []).length
    ? `<span class="exec-lang-badge">${esc((data.languages||[]).map(l=>l.charAt(0).toUpperCase()+l.slice(1)).join(', '))}</span>`
    : '';

  el('exec-content').innerHTML = `
    <div class="posture-banner">
      <div class="posture-large posture-${esc(posture)}">${esc(posture)}</div>
      <div style="flex:1">
        <div class="posture-label">Overall Compliance Posture</div>
        <div class="posture-desc">Evidence-first evaluation of ${(data.control_findings||[]).length} FDIC 370 controls across ${esc(String(data.files_analyzed||0))} file(s).</div>
        <div class="exec-badges">${langBadge}${durBadge}</div>
      </div>
    </div>
    ${statsRow}
    <div class="exec-two-col">
      <div class="info-card">
        <div class="info-card-title">Top Critical Gaps</div>
        <ul class="gap-list">${gapsHtml}</ul>
      </div>
      <div class="info-card">
        <div class="info-card-title">Immediate Priorities</div>
        <ul class="priority-list">${prioHtml}</ul>
      </div>
    </div>`;
}

function statCard(label, value, cls) {
  return `<div class="coverage-stat-card"><div class="coverage-stat-label">${esc(label)}</div><div class="coverage-stat-value ${esc(cls)}">${esc(String(value))}</div></div>`;
}

// 
// CONTROL COVERAGE
// 
function renderCoverageStats(data) {
  const cs = data.control_findings || [];
  const total    = cs.length;
  const passN    = cs.filter(f => f.status === 'PASS').length;
  const partialN = cs.filter(f => f.status === 'PARTIAL').length;
  const failN    = cs.filter(f => f.status === 'FAIL').length;
  const pct      = total ? ((passN / total) * 100).toFixed(1) : '0.0';

  // Category prefix → human-readable label mapping (7 FDIC 370 JSON control groups)
  const CAT_LABELS = {
    'R-CTL': 'Control Requirements',
    'R-DQ':  'Data Quality Thresholds',
    'R-DOC': 'Documentation Requirements',
    'R-EC':  'Enumeration Constraints',
    'R-RI':  'Referential Integrity',
    'R-TL':  'Update Timeline Requirements',
    'R-UPD': 'Update Requirements'
  };

  // Build category breakdown grouped by control_id 2-segment prefix (R-CTL, R-DQ, etc.)
  const catMap = {};
  cs.forEach(f => {
    const parts = (f.control_id || '').split('-');
    const prefix = parts.length >= 3 ? parts.slice(0, 2).join('-') : (parts[0] || 'Unknown');
    const cat = CAT_LABELS[prefix] || prefix || 'Unknown';
    if (!catMap[cat]) catMap[cat] = { pass: 0, partial: 0, fail: 0 };
    if (f.status === 'PASS')    catMap[cat].pass++;
    else if (f.status === 'PARTIAL') catMap[cat].partial++;
    else catMap[cat].fail++;
  });

  const catRows = Object.entries(catMap).sort((a,b) => a[0].localeCompare(b[0])).map(([cat, c]) => {
    const catTotal = c.pass + c.partial + c.fail;
    const pPct = catTotal ? (c.pass / catTotal * 100).toFixed(1) : '0.0';
    return `<tr>
      <td class="cov-cat">${esc(cat)}</td>
      <td class="cov-num">${catTotal}</td>
      <td class="cov-num pass-color">${c.pass}</td>
      <td class="cov-num partial-color">${c.partial}</td>
      <td class="cov-num fail-color">${c.fail}</td>
      <td class="cov-pct-cell"><div class="cov-pct-wrap"><div class="cov-pct-bar" style="width:${pPct}%"></div><span class="cov-pct-num">${pPct}%</span></div></td>
    </tr>`;
  }).join('');

  el('coverage-content').innerHTML = `
    <div class="coverage-stats-grid">
      ${statCard('PASS',    passN,    'pass-color')}
      ${statCard('PARTIAL', partialN, 'partial-color')}
      ${statCard('FAIL',    failN,    'fail-color')}
      ${statCard('TOTAL',   total,    'total-color')}
    </div>
    <div class="compliance-bar-container">
      <div class="compliance-bar-label">
        <span>Compliance Rate (PASS only)</span>
        <span class="compliance-bar-pct">${pct}%</span>
      </div>
      <div class="compliance-bar-track">
        <div class="compliance-bar-fill" style="width:${pct}%"></div>
      </div>
    </div>
    <div class="category-breakdown">
      <div class="category-breakdown-title">Coverage by Category</div>
      ${catRows
        ? `<table class="cov-table">
            <thead><tr>
              <th class="cov-th-cat">Category</th>
              <th class="cov-th-num">Controls</th>
              <th class="cov-th-num pass-color">&#10003;&nbsp;Pass</th>
              <th class="cov-th-num partial-color">&#9680;&nbsp;Partial</th>
              <th class="cov-th-num fail-color">&#10007;&nbsp;Fail</th>
              <th class="cov-th-pct">Compliance</th>
            </tr></thead>
            <tbody>${catRows}</tbody>
          </table>`
        : '<div class="placeholder-text">No category data.</div>'}
    </div>`;
}

// 
// DETAILED FINDINGS
// 
function renderDetailedFindings(findings) {
  if (!findings || findings.length === 0) {
    el('details-content').innerHTML = '<p class="placeholder-text">No findings available.</p>';
    return;
  }

  const toolbar = `
    <div class="detail-toolbar" id="detail-toolbar">
      <div class="detail-toolbar-left">
        <button class="detail-filter-btn active-all" data-dfilter="">All</button>
        <button class="detail-filter-btn" data-dfilter="PASS">PASS</button>
        <button class="detail-filter-btn" data-dfilter="PARTIAL">PARTIAL</button>
        <button class="detail-filter-btn" data-dfilter="FAIL">FAIL</button>
        <select id="detail-sev-filter" class="filter-select" style="margin-left:8px">
          <option value="">All Severities</option>
          <option value="Severe">Severe</option>
          <option value="High">High</option>
          <option value="Medium">Medium</option>
          <option value="Low">Low</option>
        </select>
      </div>
      <div class="detail-toolbar-right">
        <input type="text" id="detail-search" class="filter-search" placeholder="Search control ID or title..."/>
        <span class="filter-counts" id="detail-counts"></span>
      </div>
    </div>
    <div id="detail-accordions"></div>`;

  el('details-content').innerHTML = toolbar;

  function getFilters() {
    const activeBtn = document.querySelector('#detail-toolbar .detail-filter-btn[class*="active-"]');
    return {
      status:   activeBtn ? (activeBtn.dataset.dfilter || '') : '',
      severity: el('detail-sev-filter').value,
      search:   el('detail-search').value.toLowerCase()
    };
  }

  document.querySelectorAll('#detail-toolbar .detail-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#detail-toolbar .detail-filter-btn').forEach(b => b.className = 'detail-filter-btn');
      const status = btn.dataset.dfilter;
      btn.classList.add(status ? 'active-' + status : 'active-all');
      buildAccordions(findings, getFilters());
    });
  });

  el('detail-sev-filter').addEventListener('change', () => buildAccordions(findings, getFilters()));
  el('detail-search').addEventListener('input',    () => buildAccordions(findings, getFilters()));

  buildAccordions(findings, { status: '', severity: '', search: '' });
}

function buildAccordions(findings, filters) {
  const { status, severity, search } = filters;
  const list = findings.filter(f => {
    if (status   && f.status   !== status)   return false;
    if (severity && f.severity !== severity) return false;
    if (search) {
      const hay = ((f.control_id || '') + ' ' + (f.title || '') + ' ' + (f.section || '')).toLowerCase();
      if (!hay.includes(search)) return false;
    }
    return true;
  });

  el('detail-counts').textContent = list.length + ' of ' + findings.length + ' controls';

  const html = list.map((f) => {
    // Use global index so row→accordion cross-navigation still works
    const idx = gFindings.findIndex(g => g.control_id === f.control_id);
    const evidenceHtml = (f.evidence || []).map(ev => {
      const hasLocation = ev.file && ev.file !== '(not in codebase)';
      const locationLine = hasLocation
        ? `<div class="evidence-file">${esc(ev.file)} &mdash; lines ${esc(String(ev.start_line || ''))}&#8211;${esc(String(ev.end_line || ''))}</div>`
        : (ev.file ? `<div class="evidence-file evidence-absent">${esc(ev.file)}</div>` : '');
      const snippetLine = ev.snippet && ev.snippet !== '(absent)'
        ? `<pre class="evidence-snippet">${esc(ev.snippet)}</pre>` : '';
      const signalBadge = ev.signal ? `<span class="evidence-signal-badge">${esc(ev.signal)}</span>` : '';
      return `<div class="evidence-item">
        <div class="evidence-item-hdr">${signalBadge}${locationLine}</div>
        ${snippetLine}
        <div class="evidence-explanation">${esc(ev.explanation || '')}</div>
      </div>`;
    }).join('') || (f.gap
      ? `<div class="evidence-item evidence-gap-fallback"><div class="evidence-explanation">${esc(f.gap)}</div></div>`
      : '<div class="placeholder-text" style="padding:8px 0">No code evidence recorded.</div>');

    const confPct = Math.round((f.confidence || 0) * 100);
    return `
      <div class="finding-accordion" id="acc-${idx}">
        <div class="accordion-header" data-acc-idx="${idx}">
          <span class="accordion-ctrl-id">${esc(f.control_id)}</span>
          <span class="accordion-title">${esc(f.title || '')}</span>
          <div class="accordion-right">
            <span class="conf-chip">${confPct}%</span>
            <span class="status-badge status-${esc(f.status)}">${esc(f.status)}</span>
            <span class="severity-badge sev-${esc(f.severity)}">${esc(f.severity)}</span>
            <svg class="accordion-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
          </div>
        </div>
        <div class="accordion-body" id="acc-body-${idx}">
          <div class="acc-meta-row">
            <span class="acc-meta-item"><span class="acc-meta-label">Rule Type</span>${esc(f.section || '—')}</span>
            <span class="acc-meta-item"><span class="acc-meta-label">Control Type</span>${esc(f.control_type || '—')}</span>
            <span class="acc-meta-item"><span class="acc-meta-label">Confidence</span>${confPct}%</span>
            <span class="acc-meta-item"><span class="acc-meta-label">Evidence</span>${(f.evidence||[]).length} items</span>
            ${(f.applicable_fields && f.applicable_fields.length) ? `<span class="acc-meta-item acc-meta-wide"><span class="acc-meta-label">Applicable Fields</span><span class="field-chips">${f.applicable_fields.map(x => `<code class="field-chip">${esc(x)}</code>`).join('')}</span></span>` : ''}
          </div>
          <div class="finding-section-label">Intent</div>
          <div class="finding-intent">${esc(f.intent || '')}</div>
          <div class="finding-section-label">Code Evidence</div>
          ${evidenceHtml}
          <div class="finding-section-label">Identified Gap</div>
          <div class="finding-gap">${f.gap ? esc(f.gap) : '<span style="color:#4a6fa5">None identified.</span>'}</div>
          <div class="finding-section-label">Remediation Guidance</div>
          <div class="finding-remediation">${f.remediation ? esc(f.remediation) : '<span style="color:#4a6fa5">No remediation guidance provided.</span>'}</div>
        </div>
      </div>`;
  }).join('');

  el('detail-accordions').innerHTML = html || '<p class="placeholder-text">No findings match this filter.</p>';

  el('detail-accordions').querySelectorAll('.accordion-header[data-acc-idx]').forEach(header => {
    header.addEventListener('click', () => {
      const i    = header.dataset.accIdx;
      const body = el('acc-body-' + i);
      const open = body.classList.contains('open');
      body.classList.toggle('open', !open);
      header.classList.toggle('open', !open);
    });
  });
}

// 
// LINEAGE
// 
function renderLineage(data) {
  const codeEdges = data.code_lineage || [];
  const dl        = data.data_lineage  || {};

  // ── Code Call Lineage table ───────────────────────────────────────────────────
  const codeHtml = codeEdges.length
    ? `<table class="lineage-call-table">
        <thead><tr>
          <th>Caller&nbsp;(Source)</th><th></th>
          <th>Callee&nbsp;(Target)</th>
          <th>Relationship</th>
        </tr></thead>
        <tbody>${codeEdges.map(e => `
          <tr>
            <td class="lcell-module">${esc(e.source || '')}</td>
            <td class="lcell-arrow">&#8594;</td>
            <td class="lcell-module">${esc(e.target || '')}</td>
            <td class="lcell-desc">${esc(e.description || '')}</td>
          </tr>`).join('')}
        </tbody>
       </table>`
    : '<div class="placeholder-text" style="padding:10px 0">No code lineage data extracted.</div>';

  // ── Informatica-style Data Lineage ───────────────────────────────────────────
  const nodes  = dl.nodes || [];
  const edges  = dl.edges || [];
  const byType = { source: [], transform: [], target: [] };
  nodes.forEach(n => { if (byType[n.type]) byType[n.type].push(n); });
  const nodeById = {};
  nodes.forEach(n => { nodeById[n.id] = n; });

  function renderLane(list, cls, icon) {
    if (!list.length) return '<div class="ln-empty">— none —</div>';
    return list.map(n => `
      <div class="lineage-node ${cls}">
        <span class="ln-icon">${icon}</span>
        <div class="ln-label">${esc(n.label || '')}</div>
        ${n.details ? `<div class="ln-details">${esc(n.details)}</div>` : ''}
      </div>`).join('');
  }

  const dataGraphHtml = nodes.length
    ? `<div class="lineage-swimlane">
        <div class="lineage-lane">
          <div class="lineage-lane-header ln-hdr-source">&#9726;&nbsp;Sources</div>
          ${renderLane(byType.source, 'ln-source', '&#9646;')}
        </div>
        <div class="lineage-lane-connector">&#8594;</div>
        <div class="lineage-lane">
          <div class="lineage-lane-header ln-hdr-transform">&#9881;&nbsp;Transforms</div>
          ${renderLane(byType.transform, 'ln-transform', '&#9650;')}
        </div>
        <div class="lineage-lane-connector">&#8594;</div>
        <div class="lineage-lane">
          <div class="lineage-lane-header ln-hdr-target">&#9728;&nbsp;Targets</div>
          ${renderLane(byType.target, 'ln-target', '&#9642;')}
        </div>
      </div>`
    : '<div class="placeholder-text">No data lineage nodes extracted.</div>';

  const connHtml = edges.length
    ? `<table class="lineage-conn-table">
        <thead><tr>
          <th>From</th><th></th><th>Relationship</th><th></th><th>To</th>
        </tr></thead>
        <tbody>${edges.map(e => {
          const fn = nodeById[e.from] || { label: e.from, type: '' };
          const tn = nodeById[e.to]   || { label: e.to,   type: '' };
          return `<tr>
            <td class="lcell-node ln-${fn.type}-txt">${esc(fn.label || e.from)}</td>
            <td class="lcell-arrow">&#8594;</td>
            <td class="lcell-rel">${esc(e.label || '')}</td>
            <td class="lcell-arrow">&#8594;</td>
            <td class="lcell-node ln-${tn.type}-txt">${esc(tn.label || e.to)}</td>
          </tr>`;
        }).join('')}
        </tbody>
      </table>`
    : '<div class="placeholder-text">No data connections extracted.</div>';

  el('lineage-content').innerHTML = `
    <div class="lineage-section-hdr">Code Call Lineage <span class="lineage-hdr-count">${codeEdges.length}&nbsp;edges</span></div>
    <div class="lineage-card" style="margin-bottom:18px">${codeHtml}</div>

    <div class="lineage-section-hdr">Data Lineage &mdash; Flow Diagram</div>
    <div class="lineage-card" style="margin-bottom:14px">${dataGraphHtml}</div>

    <div class="lineage-section-hdr">Data Connections</div>
    <div class="lineage-card">${connHtml}</div>`;
}

function buildEntryPoints(findings) {
  const files = new Set();
  findings.forEach(f => (f.evidence || []).forEach(e => { if (e.file) files.add(e.file); }));
  if (files.size === 0) return '<div class="placeholder-text" style="padding:8px 0">No entry-point data extracted.</div>';
  return Array.from(files).map(f => `<div class="lineage-edge"><span class="lineage-from">${esc(f)}</span></div>`).join('');
}

// 
// REMEDIATION PLAN
// 
function renderRemediationPlan(rp) {
  if (!rp) {
    el('remediation-content').innerHTML = '<p class="placeholder-text">No remediation plan available.</p>';
    return;
  }

  const phases = [
    { key: 'phase1_critical',   label: 'Phase 1 — Immediate',  desc: 'Critical deficiencies to remediate within 30 days', cls: 'phase-1' },
    { key: 'phase2_structural', label: 'Phase 2 — Near-Term',   desc: 'High-priority improvements within 90 days',         cls: 'phase-2' },
    { key: 'phase3_governance', label: 'Phase 3 — Strategic',   desc: 'Long-term architecture and process improvements',   cls: 'phase-3' }
  ];

  const blocksHtml = phases.map(ph => {
    const items = rp[ph.key] || [];
    const itemsHtml = items.map((item, i) => `
      <div class="remediation-item">
        <div class="rem-priority">${i + 1}</div>
        <div class="rem-content">
          <div class="rem-action">${esc(item.action || '')}</div>
          <div class="rem-rationale">${esc(item.rationale || '')}</div>
          ${(item.control_ids || []).length ? '<div class="rem-controls">' + item.control_ids.map(c => `<span class="rem-ctrl-tag">${esc(c)}</span>`).join('') + '</div>' : ''}
        </div>
      </div>`).join('') || '<div class="remediation-item"><div class="rem-content"><div class="rem-action">No items in this phase.</div></div></div>';

    return `
      <div class="phase-block ${ph.cls}">
        <div class="phase-header">
          <span class="phase-badge">${esc(ph.label)}</span>
          <span class="phase-title">${esc(ph.desc)}</span>
        </div>
        <div class="phase-body">${itemsHtml}</div>
      </div>`;
  }).join('');

  el('remediation-content').innerHTML = blocksHtml;
}

// 
// INIT
// 
showSection('analyze');
