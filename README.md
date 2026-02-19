# 🛡️ Kratos Agentic Code Analyzer

**Kratos Agentic Code Analyzer** is a **RAG + LangGraph powered compliance-aware code analysis platform** that scans application and infrastructure code to generate **regulatory-aligned narratives, inline controls, and risk ratings**.

It is purpose-built for **banking, financial services, and regulated environments**, with first-class support for:

- **FDIC Part 330 / 12 CFR Part 370**
- **OWASP Top 10 / ASVS**
- **NIST SP 800-53**
- **Conditional PCI-DSS / GLBA (if in scope)**

> ⚠️ Kratos is an **analysis and decision-support tool**, not a legal certification engine.

---

## ✨ Key Capabilities

- 📂 **Analyze local files** (upload or paste code)
- 🌐 **Analyze GitHub files or full repositories**
- 🧠 **Agentic reasoning** using LangGraph (retrieval → heuristics → LLM)
- 📚 **RAG-backed findings** grounded in real regulation text
- 🧾 **Inline controls** mapped to regulatory clauses
- 🚦 **Qualitative risk ratings**  
  _Very Low · Low · Moderate · Elevated · Severe_
- 🛑 **Anti-hallucination guardrails**
  - No invented regulation counts
  - No unsupported subsection claims
  - PCI/GLBA always conditional

---

## 🖼️ Screenshots

> _Add screenshots here once deployed_

### 🔍 Code Analysis View
![Code Analysis Screenshot](docs/screenshots/code-analysis.png)

### 📊 Inline Controls Mapping
![Inline Controls Screenshot](docs/screenshots/inline-controls.png)

### 🧠 Reasoning Trace (Agent Output)
![Reasoning Trace Screenshot](docs/screenshots/reasoning-trace.png)

### 🗂️ Repository-Level Summary
![Repo Summary Screenshot](docs/screenshots/repo-summary.png)

---

## 🏗️ Architecture Overview

```text
User / CI Pipeline
        |
        v
Frontend (SPA)
        |
        v
FastAPI Backend
        |
        v
LangGraph Orchestrator
   ├─ Regulation Retrieval (FAISS + Embeddings)
   ├─ Local Static Analysis (AST + Heuristics)
   └─ LLM Analyst (JSON-only output)
        |
        v
Structured Compliance Findings
```

---

## 📁 Repository Structure

```text
kratos_v3/
├─ backend/
│  ├─ main.py                 # FastAPI entrypoint
│  ├─ config.py               # Env & runtime config
│  ├─ models/
│  │  └─ outputs.py           # Pydantic output schemas
│  ├─ rag/
│  │  └─ regulation_store.py  # FDIC / OWASP / NIST ingestion + FAISS
│  └─ agents/
│     ├─ graph.py             # LangGraph orchestration
│     ├─ state.py             # Agent state definition
│     └─ tools.py             # Analysis helpers
├─ frontend/
│  ├─ index.html              # UI layout
│  ├─ styles.css              # Dark theme
│  └─ app.js                  # SPA logic
├─ regulations/               # Auto-downloaded & indexed
├─ Pipfile
├─ Pipfile.lock
└─ .env
```

---

## ⚙️ How It Works

### 1️⃣ Input Normalization
- Detect language
- Read source
- Compute LOC & metadata

### 2️⃣ Agentic Analysis Flow
LangGraph coordinates:

1. **Regulation Retrieval**
   - Query FAISS index for relevant FDIC / OWASP / NIST excerpts
2. **Local Analyzer**
   - AST parsing
   - Heuristic signals (SQL usage, auth, logging, limits, etc.)
3. **LLM Analyst**
   - Receives:
     - Source code
     - Heuristics
     - Retrieved regulation snippets
   - Produces **strict JSON output only**

### 3️⃣ Structured Output
- Narrative Summary
- Inline Controls (with evidence)
- Qualitative Risk Rating
- Reasoning Trace

---

## 🔌 API Endpoints

### Health
```http
GET /api/health
```

### Analyze Pasted Code
```http
POST /api/analyze/text
```

### Analyze Uploaded File
```http
POST /api/analyze/file
```

### Analyze GitHub File
```http
POST /api/analyze/github/file
```

### Analyze GitHub Repository
```http
POST /api/analyze/github/repo
```

---

## 🖥️ Frontend Features

- Dark-themed SPA
- Sidebar navigation
- Sections:
  - Analysis
  - Summary
  - Inline Controls
  - Reasoning Trace
- Real-time rendering of agent outputs

---

## 🚀 Setup & Run

### Prerequisites
- Python 3.10+
- Pipenv (or virtualenv)
- OpenAI API key
- Optional GitHub token

### Environment Variables (`.env`)
```env
OPENAI_MODEL=gpt-4.1-mini
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small
GITHUB_TOKEN=ghp_...   # optional
REGULATIONS_DIR=./regulations
```

### Install Dependencies
```bash
pipenv install
```

### Run Server
```bash
pipenv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

- UI: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## 🧪 Example Use Cases

- FDIC Part 370 readiness reviews
- Secure coding gap analysis
- Internal audit & RCSA evidence generation
- CI/CD compliance gating
- Vendor / third-party code assessments

---

## 🔧 Extensibility

- Plug in additional regulations (SOX, SOC2, ISO 27001)
- Map findings to internal control libraries
- Export results to GRC tools
- Integrate with CI/CD pipelines
- Add policy-as-code enforcement

---

## ⚠️ Caveats

- Kratos provides **engineering analysis**, not legal certification
- Findings depend on visible code and retrieved regulation text
- Always involve compliance/legal teams for regulatory decisions

---

## 📜 License
TBD (Internal / Enterprise / Open Source)

---

## 🤝 Contributing
Internal project – contribution guidelines coming soon.
