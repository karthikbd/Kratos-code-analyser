# Kratos - FDIC 370 Compliance Analyzer

Kratos is a **RAG + LangGraph powered compliance analysis platform** purpose-built for banking engineering teams. It scans application source code against **FDIC 12 CFR Part 370** (and supporting regulations) and produces evidence-backed compliance reports, Informatica-style data lineage graphs, and prioritised three-phase remediation plans.

> Kratos is an analysis and decision-support tool, not a legal certification engine.

---

## Key Capabilities

- **86-control FDIC 370 library**  every control from 12 CFR Part 370, organised across 12 categories
- **Parallel async analysis**  controls are batched in groups of 15 and analysed concurrently via `asyncio.gather`
- **RAG-grounded findings**  every finding is backed by regulation text retrieved from a live FAISS vector store
- **Informatica-style data lineage**  sources, transforms, and targets rendered in a three-lane swimlane, plus a connections table
- **Code call lineage**  caller  callee chains with relationship types extracted from AST heuristics
- **Coverage table**  12-category compliance table (Pass / Partial / Fail counts + % compliance)
- **Prioritised remediation plan**  Phase 1 Critical, Phase 2 Structural, Phase 3 Governance
- **Multi-input modes**  paste code, upload file(s), or point at a GitHub URL
- **General-purpose analyzer** included for OWASP / NIST / GLBA narrative alongside FDIC 370

---

## Architecture

```
User (Browser)
      
      
Frontend (HTML/CSS/JS  frontend/)
        REST /api/*
      
FastAPI  (backend/main.py)
      
       General Analyzer (POST /api/analyze/**)
               LangGraph: retrieve  heuristics  LLM
      
       FDIC 370 Analyzer (POST /api/analyze/fdic370/**)
                
                 FAISS Vector Store  (backend/rag/regulation_store.py)
                     FDIC 370 + NIST + OWASP text chunks, cached per process
                
                 86-control parallel batch engine  (backend/agents/graph.py)
                     asyncio.gather( batch_0..batch_5 )  per-control findings
                
                 Synthesis LLM call  (graph.py _synthesize)
                          
                   FDIC370Analysis  (backend/models/outputs.py)
```

---

## Repository Structure

```
kratos_v3/
 backend/
    main.py                  # FastAPI app  all 8 API endpoints
    config.py                # Env-driven config (OPENAI_*, GITHUB_TOKEN, )
    agents/
       graph.py             # LangGraph pipeline, 86-control library, synthesis
       tools.py             # ast_summary(), heuristic_signals()
       state.py             # AgentState TypedDict
    models/
       outputs.py           # All Pydantic DTOs (see Models section)
    rag/
        regulation_store.py  # FAISS builder + retrieve_regulation_chunks()
 frontend/
    index.html               # SPA shell
    app.js                   # All render logic (635 lines)
    styles.css               # Dark-theme styles (1 240 lines)
 regulations/
    fdic_370.txt
    fdic_it_guide.txt
    nist_800_53.txt
    owasp_secure_code.txt
 sample_test_code/            # Five Python scripts with deliberate violations
    deposit_service.py       # RC, OC, RNC, IA, P330, DR controls
    data_layer.py            # AT, DT controls
    business_logic.py        # TD, OR, TC controls
    auth_service.py          # SA controls
    api_endpoints.py         # OR, TD, SA controls
 Pipfile
 README.md
```

---

## FDIC 370 Control Library  86 Controls / 12 Categories

| Prefix | Category | Controls |
|--------|----------|----------|
| RC | Record Completeness | 12 |
| OC | Ownership & Capacity | 10 |
| RNC | Record Nomenclature & Classification | 8 |
| IA | Information Architecture | 10 |
| P330 | Part 330 Deposit Insurance | 8 |
| DR | Data Retention | 6 |
| AT | Auditability & Traceability | 6 |
| DT | Data Transformation | 5 |
| TD | Technology Dependencies | 6 |
| TC | Technical Controls | 5 |
| OR | Operational Resilience | 5 |
| SA | Security Architecture | 5 |

Each control carries: `id`, `name`, `section` (CFR citation), `description`, and `category`.

---

## API Endpoints

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Returns `{status, model, embedding_model}` |

### General Analyzer

| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/api/analyze/text` | `{code, filename?}` | Paste code for general analysis |
| POST | `/api/analyze/file` | multipart `file` | Upload a file for general analysis |
| POST | `/api/analyze/github/file` | `{url}` | Analyze a single GitHub file URL |
| POST | `/api/analyze/github/repo` | `{url}` | Analyze all supported files in a GitHub repo |

### FDIC 370 Analyzer

| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/api/analyze/fdic370/files` | multipart `files[]` | Upload one or more files  FDIC 370 report |
| POST | `/api/analyze/fdic370/text` | `{code, filename?}` | Paste code  FDIC 370 report |
| POST | `/api/analyze/fdic370/github` | `{url}` | GitHub file or repo  FDIC 370 report |

All FDIC 370 endpoints return a `FDIC370Analysis` JSON object (see Models section).

---

## Output Models

```python
# backend/models/outputs.py (simplified)

class FDICControlFinding(BaseModel):
    control_id: str            # e.g. "RC-001"
    control_name: str
    status: str                # "pass" | "partial" | "fail" | "not_applicable"
    confidence: float          # 0.0  1.0
    evidence: List[str]        # Lines / snippets from the analysed code
    gaps: List[str]            # What is missing
    section: str               # CFR citation
    category: str

class FDICCoverageStats(BaseModel):
    total_controls: int
    passed: int
    partial: int
    failed: int
    not_applicable: int
    compliance_percentage: float
    category_breakdown: Dict[str, Any]

class FDICExecutiveSummary(BaseModel):
    overall_risk_level: str    # Critical | High | Medium | Low | Minimal
    key_strengths: List[str]
    critical_gaps: List[str]
    immediate_actions: List[str]
    regulatory_exposure: str

class FDICCodeLineageEdge(BaseModel):
    source: str
    target: str
    relationship: str
    description: str

class FDICDataLineageNode(BaseModel):
    id: str
    label: str
    type: str       # "source" | "transform" | "target"
    details: str

class FDICDataLineageEdge(BaseModel):
    from_node: str  # serialised as "from"
    to_node: str    # serialised as "to"
    label: str

class FDICDataLineage(BaseModel):
    nodes: List[FDICDataLineageNode]
    edges: List[FDICDataLineageEdge]

class FDICRemediationItem(BaseModel):
    title: str
    description: str
    control_ids: List[str]
    effort: str
    impact: str

class FDICRemediationPlan(BaseModel):
    phase1_critical: List[FDICRemediationItem]
    phase2_structural: List[FDICRemediationItem]
    phase3_governance: List[FDICRemediationItem]

class FDIC370Analysis(BaseModel):
    repository_name: str
    analysis_timestamp: str
    files_analyzed: List[str]
    executive_summary: FDICExecutiveSummary
    control_findings: List[FDICControlFinding]
    coverage_stats: FDICCoverageStats
    code_lineage: List[FDICCodeLineageEdge]
    data_lineage: FDICDataLineage
    remediation_plan: FDICRemediationPlan
    raw_llm_output: str
```

---

## Data Lineage Schema

The synthesis LLM is required to emit `data_lineage` in a **graph format**:

```json
{
  "data_lineage": {
    "nodes": [
      { "id": "src_accounts", "label": "accounts table", "type": "source",    "details": "Core deposit accounts" },
      { "id": "trx_normalize","label": "normalise()",    "type": "transform", "details": "Strip PII fields" },
      { "id": "tgt_report",   "label": "fdic_report",   "type": "target",    "details": "FDIC 370 output file" }
    ],
    "edges": [
      { "from": "src_accounts", "to": "trx_normalize", "label": "feeds" },
      { "from": "trx_normalize","to": "tgt_report",    "label": "writes" }
    ]
  }
}
```

The frontend renders this as a **three-lane Informatica-style swimlane** (Sources | Transforms | Targets) plus a **data connections table** showing every edge.

---

## Frontend UI Sections

All sections are rendered in `frontend/app.js` and styled in `frontend/styles.css`.

| Section | Render Function | Description |
|---------|----------------|-------------|
| Executive Summary | `renderExecutiveSummary()` | Risk level badge, strengths, gaps, immediate actions |
| Control Coverage | `renderCoverageStats()` | 12-row table: category, total, Pass/Partial/Fail counts, % compliance |
| Findings Table | `renderFindings()` | Sortable table of all 86 control findings with evidence |
| Code Call Lineage | `renderLineage()`  call table | Caller  Callee + relationship column |
| Data Lineage Swimlane | `renderLineage()`  swimlane | Three-lane Informatica flow (Sources / Transforms / Targets) |
| Data Connections | `renderLineage()`  connections table | From  Relationship  To for every edge |
| Remediation Plan | `renderRemediationPlan()` | Phase 1 Critical / Phase 2 Structural / Phase 3 Governance cards |

### Coverage Table CSS Classes

`.cov-table`, `.cov-th-cat`, `.cov-th-num`, `.cov-th-pct`, `.cov-cat`, `.cov-num`, `.cov-pct-cell`, `.cov-pct-wrap`, `.cov-pct-bar`, `.cov-pct-num`

### Lineage CSS Classes

`.lineage-swimlane`, `.lineage-lane`, `.lineage-lane-header`, `.ln-hdr-source/transform/target`, `.lineage-node`, `.ln-source/transform/target`, `.lineage-call-table`, `.lineage-conn-table`

---

## Performance Design

| Technique | Detail |
|-----------|--------|
| FAISS singleton | Vector store built once at startup and cached in-process memory |
| Regulation chunk cache | `lru_cache` on `retrieve_regulation_chunks()` per query string |
| Parallel control batches | 86 controls  6 batches of 15 controls, all fired with `asyncio.gather` |
| Synthesis concurrency | Synthesis LLM call runs after all batch futures resolve |
| Async endpoints | All FDIC 370 endpoints are `async def`; uses `asyncio.get_event_loop().run_until_complete` for LangGraph execution |

---

## Sample Test Code

Five Python files in `sample_test_code/` contain **deliberate FDIC 370 violations** designed to exercise Kratos.

| File | Controls Targeted | Notable Issues |
|------|------------------|---------------|
| `deposit_service.py` | RC, OC, RNC, IA, P330, DR | Missing depositor-level record granularity, no ownership-change audit trail, PII in logs |
| `data_layer.py` | AT, DT | No query audit logging, lossy decimal-to-float transform |
| `business_logic.py` | TD, OR, TC | Hard-coded third-party dependency, no fallback on vendor failure |
| `auth_service.py` | SA | Weak password hashing (MD5), no MFA, tokens never expire |
| `api_endpoints.py` | OR, TD, SA | No rate limiting, missing auth on admin endpoints, debug mode forced on |

Cross-file import chain (for lineage extraction):  
`api_endpoints`  `business_logic`  `auth_service` + `data_layer`  `deposit_service`

Each file includes a `# CALL_GRAPH:` annotation block to assist AST-based lineage extraction.

---

## Setup & Run

### 1. Prerequisites

- Python 3.10+
- [Pipenv](https://pipenv.pypa.io/)
- An OpenAI API key

### 2. Install dependencies

```bash
pipenv install --dev
pipenv shell
```

### 3. Configure environment

Create a `.env` file in the repo root:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
EMBEDDING_MODEL=text-embedding-3-small
REGULATIONS_DIR=./regulations
# Optional  only needed for GitHub repo analysis
GITHUB_TOKEN=ghp_...
```

### 4. Start the server

```bash
pipenv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

On first startup, `ensure_regulations_ready()` will verify/download regulation source files into `regulations/`.

### 5. Open the UI

```
http://localhost:8000
```

The frontend is served as static files mounted at `/static` and aliased to `/`.

---

## Development Notes

### Key conventions

- **Descriptive-only policy**  the LLM analyst must NOT propose fixes, add evaluative labels, or use PASS/FAIL language beyond the JSON status field. See `node_llm_analyst` / `_SYNTHESIS_TEMPLATE` in `graph.py`.
- **Use provided extractors**  call `ast_summary()` and `heuristic_signals()` from `tools.py`; do not re-implement heuristics.
- **Return shape contract**  all output fields must match the Pydantic models in `outputs.py`. If you change a field, update the model and any frontend render function that reads it.
- **Regulation sourcing**  use `retrieve_regulation_chunks(query, k)` for regulation context; do not hardcode regulation text into prompts.

### Adding a new control

1. Add an entry to `FDIC_370_CONTROLS` in `graph.py` with `id`, `name`, `section`, `description`, `category`.
2. If introducing a new category prefix, add it to `CAT_LABELS` in `frontend/app.js`.
3. Update `FDICCoverageStats.category_breakdown` if needed.

### Project constraints

- Do not add new heavy dependencies without discussion; `langchain`, `langchain_community`, and `faiss-cpu` are already present.
- Maintain Codacy clean status  run `codacy_cli_analyze` after every file edit.

---

## Regulations Bundled

| File | Regulation |
|------|-----------|
| `fdic_370.txt` | 12 CFR Part 370  Recordkeeping for Timely Deposit Insurance |
| `fdic_it_guide.txt` | FDIC IT Examination Handbook |
| `nist_800_53.txt` | NIST SP 800-53 Rev 5  Security & Privacy Controls |
| `owasp_secure_code.txt` | OWASP Secure Coding Practices |

---

## License

Internal / proprietary  PNC Financial Services. Not for public distribution.
