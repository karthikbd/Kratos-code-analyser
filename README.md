# Kratos Code & Compliance Analyzer

**FDIC Part 370 Deep Compliance Scanner — AI-Powered Regulatory Code Analysis**

---

## Table of Contents

1. [Business Overview](#business-overview)
2. [What Problem Does This Solve?](#what-problem-does-this-solve)
3. [Key Capabilities](#key-capabilities)
4. [Technical Architecture](#technical-architecture)
5. [Technology Stack](#technology-stack)
6. [Project Structure](#project-structure)
7. [Requirements](#requirements)
8. [Run Guide](#run-guide)
9. [Operational Systems](#operational-systems)
10. [Regulatory Coverage](#regulatory-coverage)
11. [API Reference](#api-reference)
12. [License](#license)

---

## Business Overview

### What is FDIC Part 370?

**12 CFR Part 370** ("Recordkeeping for Timely Deposit Insurance Determination") is a federal regulation requiring covered institutions (banks with 2+ million deposit accounts or $20+ billion in deposits) to maintain complete, accurate, and up-to-date records so the FDIC can determine deposit insurance coverage within **24 hours** of a bank failure.

When a bank fails, the FDIC must quickly calculate how much each depositor is insured for. This requires:

- **Knowing the ownership category** of every account (single, joint, trust, retirement, etc.)
- **Aggregating balances correctly** across all accounts per depositor per ownership category
- **Applying the Standard Maximum Deposit Insurance Amount (SMDIA)** — currently $250,000
- **Generating output files** in the FDIC's prescribed format (pipe-delimited ASCII)
- **Identifying unresolvable accounts** and routing them to a "pending" file with reason codes

Failure to comply can result in enforcement actions, delayed payouts to depositors, and systemic risk during bank resolution events.

### What is Kratos?

**Kratos** is an AI-powered deep code analyzer that scans a bank's actual operational source code — COBOL, Java, SQL, Python, JCL, shell scripts, configuration files, and data files — to determine whether the bank's systems can actually perform FDIC Part 370 compliance calculations correctly.

Unlike checklist-based compliance tools, Kratos reads and analyzes the **real code** that runs in production, identifying:

- Missing ownership right capacity (ORC) classifications
- Incorrect insurance calculation logic
- Data completeness gaps (orphan accounts, missing beneficiary info)
- Output file format violations
- Runtime performance issues (can the system meet the 24-hour deadline?)
- Data lineage breaks across system boundaries

### Why Does This Matter?

| Traditional Compliance | Kratos Approach |
|----------------------|-----------------|
| Manual checklists and interviews | Automated source code analysis |
| Self-reported by the bank | Evidence-based from actual code |
| Annual review cycle | On-demand, repeatable scans |
| Misses code-level gaps | Finds bugs regulators would find |
| No data lineage tracking | Traces data flow across systems |
| Compliance ≠ working code | Validates code actually works |

---

## What Problem Does This Solve?

Banks typically have **legacy operational systems** (some 30+ years old) that were never designed with FDIC Part 370 in mind. These systems have:

1. **Hardcoded SMDIA limits** that don't update when regulations change
2. **Missing ORC types** — the code handles single/joint but ignores irrevocable trusts or employee benefit plans
3. **Per-account calculations** instead of per-depositor aggregation across all accounts
4. **No beneficiary tracking** for revocable trust accounts
5. **Stale OFAC screening lists** that don't meet real-time requirements
6. **Data silos** where customer data doesn't flow correctly between systems
7. **No 24-hour processing capability** — batch jobs take 48+ hours

Kratos finds these issues automatically by analyzing the source code, not by asking people.

---

## Key Capabilities

### 7-Layer Analysis Pipeline

Each layer mirrors a section of the FDIC's own compliance review methodology:

| Layer | Name | Regulatory Source | What It Checks |
|-------|------|-------------------|----------------|
| **1** | ORC Assignment Logic | 12 CFR Part 330 + IT Guide §4 | All 11 ORC types handled, fallback logic, pending routing |
| **2** | Data Completeness | IT Guide §2.3.2–2.3.3 | Orphan accounts, conditional field validation, government collateral |
| **3** | Calculation Engine | Compliance Manual §6, §10 | Depositor+ORC aggregation, interest accrual, debt offset, death-of-owner |
| **4** | Output File Pipeline | IT Guide §5 + Appendix A | 4 output files format, data lineage, pending file entries, ARE validation |
| **5** | Behavioral / Runtime | Compliance Manual §4, §5 | 24-hour deadline, account restriction speed, failover, throughput |
| **6** | Certification Artifacts | 12 CFR 370.10(a) + Appendix B | Per-ORC scoring, pending file reports, data quality logs |
| **7** | Data Lineage | IT Guide §3 + §5 | Source-to-output data flow, transformation tracking, cross-system tracing |

### AI-Enhanced Analysis

- **GPT-4.1-mini** generates remediation advice for every finding
- **RAG Pipeline** (FAISS vector store) grounds analysis in actual regulatory text from 4 FDIC documents
- **LangGraph StateGraph** orchestrates multi-agent analysis with real-time streaming

### Compliance Control Library

The control library is derived from **four regulatory sources** and is **system-independent** — the same set of controls is evaluated against every operational system. What changes per system is which controls **pass or fail**, not the control catalog itself. The actual count is determined at runtime from the `CONTROL_LIBRARY` in `backend/controls/__init__.py`.

To check the current control count:
```bash
pipenv run python -c "from backend.controls import CONTROL_LIBRARY; print(len(CONTROL_LIBRARY))"
```

Regulatory sources:
- **12 CFR Part 370** — Core recordkeeping requirements
- **12 CFR Part 330** — Deposit insurance coverage rules
- **12 CFR 360.8** — Method for determining coverage at failure
- **FDIC IT Functional Guide v3.0** — Technical implementation specifications

### Live Interactive UI

- Real-time WebSocket pipeline visualization
- Agent-by-agent progress tracking with findings
- Control library with pass/fail validation
- Interactive data lineage graph (ReactFlow)
- RAG coverage comparison panel
- Multi-system switching for different analysis scenarios
- Source file / line number / code snippet references on every finding

---

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         KRATOS CODE ANALYZER                        │
│                    FDIC Part 370 Compliance Pipeline                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │  React UI    │◄──►│  FastAPI      │◄──►│  LangGraph           │  │
│  │  (Vite)      │ WS │  Server       │    │  Orchestrator        │  │
│  │  Port 5173   │    │  Port 8001    │    │  (StateGraph)        │  │
│  └──────────────┘    └──────┬───────┘    └──────────┬───────────┘  │
│                             │                        │              │
│                    ┌────────▼────────┐    ┌──────────▼───────────┐  │
│                    │  REST API       │    │  7 Analysis Layers    │  │
│                    │  /api/run       │    │                       │  │
│                    │  /api/systems   │    │  L1: ORC Assignment   │  │
│                    │  /api/controls  │    │  L2: Data Complete    │  │
│                    │  /api/lineage   │    │  L3: Calc Engine      │  │
│                    │  /ws            │    │  L4: Output Pipeline  │  │
│                    └────────────────┘    │  L5: Behavioral       │  │
│                                          │  L6: Certification    │  │
│                    ┌────────────────┐    │  L7: Data Lineage     │  │
│                    │  RAG Pipeline  │    └───────────────────────┘  │
│                    │  FAISS Index   │                                │
│                    │  4 FDIC Docs   │    ┌───────────────────────┐  │
│                    │  Auto-chunked  │    │  Operational Systems   │  │
│                    └────────────────┘    │  (Auto-discovered)     │  │
│                                          │                        │  │
│                    ┌────────────────┐    │  ├── legacy_deposit/   │  │
│                    │  GPT-4.1-mini  │    │  ├── wire_transfer/    │  │
│                    │  (OpenAI API)  │    │  └── trust_custody/    │  │
│                    │  Remediation   │    └────────────────────────┘  │
│                    └────────────────┘                                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Source Code Files          Analysis Pipeline             Output
─────────────────         ──────────────────         ─────────────
.cob .java .sql           ┌───────────────┐         Findings
.py .jcl .sh    ────────► │  7 Layers     │ ──────► (with source refs)
.properties .csv          │  + GPT AI     │         
                          │  + RAG        │         Controls
                          └───────┬───────┘         (pass/fail)
                                  │                  
                                  ▼                 Data Lineage
                          ┌───────────────┐         (graph)
                          │  WebSocket    │         
                          │  Stream       │ ──────► Real-time UI
                          └───────────────┘         (live agents)
```

### Component Interaction

| Component | Role | Protocol |
|-----------|------|----------|
| **React Frontend** | Interactive dashboard, pipeline visualization | HTTP + WebSocket |
| **FastAPI Server** | API gateway, pipeline orchestration, state management | REST + WS on port 8001 |
| **LangGraph Orchestrator** | Coordinates 7 analysis agents via StateGraph | In-process Python |
| **Analysis Layers (1–7)** | Deterministic code analysis per regulatory section | Function calls |
| **GPT-4.1-mini** | AI remediation advice, severity assessment | OpenAI API |
| **FAISS RAG** | Retrieval-Augmented Generation from regulatory docs | In-process vector search |
| **Operational Systems** | Target codebases to analyze (auto-discovered) | File system scan |

---

## Technology Stack

### Backend

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Runtime | Python 3.11+ | Core language |
| LLM | OpenAI GPT-4.1-mini | AI-powered remediation and analysis |
| Agent Framework | LangChain + LangGraph | Multi-agent orchestration |
| Vector Store | FAISS (faiss-cpu) | RAG document retrieval |
| Data Models | Pydantic v2 | Type-safe models, validation |
| Web Framework | FastAPI + Uvicorn | REST API + WebSocket server |
| CLI | Typer + Rich | Command-line interface |
| Graph Analysis | NetworkX | Data lineage graph computation |
| Data Analysis | pandas | Tabular data processing |
| HTTP Client | httpx | External API calls |
| Tokenizer | tiktoken | Token counting for LLM inputs |

### Frontend

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | React 19 + TypeScript | UI framework |
| Build Tool | Vite 4.5 | Dev server + bundler |
| Flow Diagrams | @xyflow/react 12 | Interactive data lineage graph |
| Animations | framer-motion 12 | Smooth UI transitions |
| Icons | lucide-react | Icon library |

---

## Project Structure

```
Kratos_code_and_compliance_analyzer/
│
├── README.md                          # This file
├── Pipfile                            # Python dependencies + run scripts
├── Pipfile.lock                       # Locked dependency versions
├── pyproject.toml                     # Build configuration (hatchling)
├── .env.example                       # Environment template
├── .env                               # Your local env (OPENAI_API_KEY)
├── Kratos POC.code-workspace          # VS Code workspace file
│
├── backend/              # ── Python Backend Package ──
│   ├── __init__.py                    # Package version
│   ├── cli.py                         # Typer CLI entry point
│   ├── server.py                      # FastAPI server (REST + WebSocket)
│   │
│   ├── core/
│   │   ├── models.py                  # Pydantic models (Finding, ORC, Summary)
│   │   └── sample_data.py             # Sample accounts with compliance gaps
│   │
│   ├── layers/                        # ── 7 Analysis Layers ──
│   │   ├── layer1_orc_static.py       # ORC Assignment Logic Analysis
│   │   ├── layer2_data_completeness.py # Data Completeness Validation
│   │   ├── layer3_calc_engine.py      # Calculation Engine Verification
│   │   ├── layer4_output_pipeline.py  # Output File Pipeline Integrity
│   │   ├── layer5_behavioral.py       # Runtime / Behavioral Compliance
│   │   ├── layer6_certification.py    # Certification Artifact Generation
│   │   └── layer7_data_lineage.py     # Data Lineage Tracing
│   │
│   ├── agents/
│   │   ├── base.py                    # Shared LLM client (GPT-4.1-mini)
│   │   └── orchestrator.py            # LangGraph StateGraph pipeline
│   │
│   ├── rag/
│   │   └── agent.py                   # RAG pipeline (FAISS build + query)
│   │
│   └── controls/
│       └── __init__.py                # FDIC compliance controls library (auto-counted)
│
├── frontend/                          # ── React Frontend ──
│   ├── package.json                   # Node.js dependencies
│   ├── vite.config.ts                 # Vite configuration
│   ├── tsconfig.json                  # TypeScript configuration
│   └── src/
│       ├── App.tsx                     # Main app (tabs, system selector, pipeline)
│       ├── main.tsx                    # React entry point
│       ├── index.css                  # Global styles
│       ├── types/
│       │   └── index.ts               # TypeScript type definitions
│       ├── hooks/
│       │   └── useWebSocket.ts        # WebSocket hook (real-time state)
│       └── components/
│           ├── SummaryBar.tsx          # Top status bar (severity, controls tally)
│           ├── AgentCards.tsx          # Agent detail cards with findings
│           ├── AgentNode.tsx           # ReactFlow agent node component
│           ├── PipelineFlow.tsx        # Pipeline visualization
│           ├── ControlLibrary.tsx      # FDIC control library (pass/fail per system)
│           └── DataLineageGraph.tsx    # Interactive data lineage graph
│
├── operational_systems/               # ── Target Systems to Analyze ──
│   ├── legacy_deposit_system/         # System 1: COBOL/Java deposit processing
│   ├── wire_transfer_system/          # System 2: Python/Java wire transfers
│   └── trust_custody_system/          # System 3: COBOL/Java trust accounts
│
└── data/                              # ── RAG Knowledge Base ──
    ├── fdic_docs/                     # Regulatory source documents
    │   ├── 12_cfr_370.txt             # Part 370 full text
    │   ├── 12_cfr_330.txt             # Part 330 full text
    │   ├── 12_cfr_360_8.txt           # 360.8 full text
    │   └── fdic_it_guide.txt          # IT Functional Guide v3.0
    └── faiss_index/                   # Pre-built FAISS vector index
```

---

## Requirements

### System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| OS | Windows 10 / macOS 12 / Linux | Windows 11 / macOS 14 |
| Python | 3.11+ | 3.11.5 (Anaconda) |
| Node.js | 16.x | 18.x or 20.x |
| npm | 8.x | 9.x+ |
| RAM | 4 GB | 8 GB |
| Disk | 500 MB | 1 GB |
| Network | Required (OpenAI API calls) | Broadband |

### API Keys

| Key | Required | Purpose |
|-----|----------|---------|
| `OPENAI_API_KEY` | **Yes** | GPT-4.1-mini for AI analysis and remediation |

### Python Dependencies (managed by Pipfile)

| Package | Version | Purpose |
|---------|---------|---------|
| pydantic | ≥2.6 | Data models and validation |
| rich | ≥13.7 | Terminal formatting |
| typer | ≥0.12 | CLI framework |
| networkx | ≥3.3 | Graph analysis |
| python-dateutil | ≥2.9 | Date parsing |
| langchain | ≥0.2 | LLM framework |
| langchain-openai | ≥0.1 | OpenAI integration |
| langchain-community | ≥0.2 | Community integrations |
| langchain-core | ≥0.2 | Core abstractions |
| langgraph | ≥0.1 | Multi-agent orchestration |
| openai | ≥1.30 | OpenAI API client |
| faiss-cpu | latest | Vector similarity search |
| tiktoken | latest | Token counting |
| httpx | ≥0.27 | HTTP client |
| pandas | ≥2.2 | Data analysis |
| fastapi | ≥0.110 | Web framework |
| uvicorn | ≥0.29 | ASGI server |
| websockets | ≥12 | WebSocket support |
| python-dotenv | latest | Environment variables |

### Node.js Dependencies (managed by package.json)

| Package | Version | Purpose |
|---------|---------|---------|
| react | ^19.2.0 | UI framework |
| react-dom | ^19.2.0 | DOM rendering |
| @xyflow/react | ^12.10.1 | Interactive flow diagrams |
| framer-motion | ^12.35.0 | Animations |
| lucide-react | ^0.577.0 | Icons |

---

## Run Guide

### Quick Start (Git Bash)

Open Git Bash and run the following commands:

```bash
# 1. Navigate to the project
cd /c/Users/karthikeyan1/PNC/Kratos_code_and_compliance_analyzer

# 2. Install Python dependencies
pipenv install

# 3. Install the package in development mode
pipenv run pip install -e .

# 4. Set up environment variables
cp .env.example .env
# Edit .env and verify your OPENAI_API_KEY is set

# 5. Start the backend server (Terminal 1)
pipenv run server

# 6. Open a NEW Git Bash terminal for the frontend
cd /c/Users/karthikeyan1/PNC/regulatory-compliance-system/frontend
npm install
npm run dev
```

### Step-by-Step Guide

#### Step 1: Install Python Dependencies

```bash
cd /c/Users/karthikeyan1/PNC/Kratos_code_and_compliance_analyzer
pipenv install
pipenv run pip install -e .
```

This creates a virtual environment and installs all Python packages from the Pipfile.

#### Step 2: Configure Environment

```bash
cp .env.example .env
```

Edit the `.env` file and ensure these values are set:

```dotenv
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4.1-mini
PYTHONIOENCODING=utf-8
VITE_WS_URL=ws://localhost:8001/ws
```

#### Step 3: Start the Backend Server

```bash
pipenv run server
```

This runs:
```
uvicorn backend.server:app --reload --host 0.0.0.0 --port 8001
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Application startup complete.
Building FAISS RAG index from 4 FDIC documents...
RAG index ready: <N> chunks indexed
```

**Keep this terminal running.**

#### Step 4: Start the Frontend Dev Server

Open a **new Git Bash terminal**:

```bash
cd /c/Users/karthikeyan1/PNC/regulatory-compliance-system/frontend
npm install       # First time only
npm run dev
```

You should see:
```
  VITE v4.5.14  ready in 300 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

#### Step 5: Open the Application

Open your browser and navigate to:

```
http://localhost:5173
```

#### Step 6: Run an Analysis

1. Select an **Operational System** from the dropdown (e.g., "Legacy Deposit System")
2. Toggle **RAG Enhancement** on/off as desired
3. Click the **"Analyze"** button
4. Watch the pipeline run in real-time via WebSocket streaming
5. View results across tabs: **Pipeline**, **Controls**, **Data Lineage**

### CLI Commands (Alternative — No UI)

You can also run analysis directly from the command line:

```bash
# Run full 7-layer analysis
pipenv run analyze

# Run a single layer (1-7)
pipenv run scan 1
pipenv run scan 3

# Generate certification artifacts
pipenv run certify

# Full pipeline with GPT remediation advice
pipenv run pipeline --gpt

# Run behavioral benchmarks
pipenv run benchmark

# Display results from saved JSON
pipenv run report results.json
```

### Stopping the Application

```bash
# In the backend terminal:  Press Ctrl+C
# In the frontend terminal: Press Ctrl+C
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | Run `pipenv run pip install -e .` to install the package |
| `OPENAI_API_KEY not set` | Check your `.env` file has a valid key |
| Frontend won't connect | Ensure backend is running on port 8001 first |
| `pipenv: command not found` | Run `pip install pipenv` |
| Port 8001 already in use | Kill the process: `lsof -i :8001` or change port in Pipfile |
| Folder rename pending | Close VS Code, run `rename_to_kratos.bat` in `C:\Users\karthikeyan1\PNC\`, reopen VS Code from new path |
| FAISS index errors | Delete `data/faiss_index/` folder and restart server (auto-rebuilds) |
| WebSocket disconnects | Refresh the browser page; connection auto-reconnects |

---

## Operational Systems

Kratos auto-discovers all systems in the `operational_systems/` directory. Each system represents a different banking domain with intentionally embedded compliance violations for the analyzer to detect.

### System 1: Legacy Deposit System

| Attribute | Detail |
|-----------|--------|
| **Domain** | Core deposit account processing |
| **Tech Stack** | COBOL, Java, SQL, JCL, Shell scripts |
| **Scenario** | Classic legacy banking — 30+ year old COBOL with modern Java overlay |
| **Key Violations** | Missing IRR/ANC ORC types, hardcoded $250K SMDIA, no beneficiary aggregation, per-account-not-per-depositor calculations |

> File count and verdict are determined dynamically at analysis time.

### System 2: Wire Transfer System

| Attribute | Detail |
|-----------|--------|
| **Domain** | Wire transfer & payment processing (FedWire, SWIFT, ACH) |
| **Tech Stack** | Python, Java, PostgreSQL, Shell scripts |
| **Scenario** | Modern payment platform with OFAC screening and cross-border routing |
| **Key Violations** | OFAC SDN list cached/stale, pending wires excluded from insurance calc, MT103 PII in memory, two-way reconciliation (not three-way), per-transaction not per-depositor |

> File count and verdict are determined dynamically at analysis time.

### System 3: Trust & Custody System

| Attribute | Detail |
|-----------|--------|
| **Domain** | Trust accounts, fiduciary services, beneficiary management |
| **Tech Stack** | COBOL, Java, SQL Server, JCL, Shell scripts |
| **Scenario** | Fiduciary trust operations — revocable/irrevocable trusts, employee benefit plans |
| **Key Violations** | Revocable/irrevocable trust confusion, EBP calc per-plan not per-participant, missing beneficiary interest allocation, grantor death flag ignored, contingent beneficiaries not distinguished |

> File count and verdict are determined dynamically at analysis time.

### Adding New Systems

To add a new operational system:

1. Create a new directory under `operational_systems/` (e.g., `operational_systems/mortgage_system/`)
2. Add a `README.md` with a description
3. Add source files (any supported extension: `.py`, `.java`, `.sql`, `.cob`, `.jcl`, `.sh`, `.properties`, `.csv`, etc.)
4. Restart the backend server — the system is automatically discovered
5. It will appear in the UI dropdown immediately

---

## Regulatory Coverage

### ORC Types (12 CFR Part 330)

| Code | Ownership Rights Capacity | SMDIA Limit |
|------|--------------------------|-------------|
| SGL | Single Ownership | $250,000 |
| JNT | Joint Ownership | $250,000 per co-owner |
| REV | Revocable Trust | $250,000 per beneficiary |
| IRR | Irrevocable Trust | $250,000 per beneficiary |
| CRA | Certain Retirement Accounts | $250,000 |
| BUS | Business/Organization | $250,000 |
| EBP | Employee Benefit Plan | $250,000 per participant |
| GOV1 | Government (Federal) | Unlimited |
| GOV2 | Government (State/Municipal) | Unlimited |
| GOV3 | Government (Tribal) | Unlimited |
| ANC | Annuity Contract | $250,000 |

### Pending Reason Codes (IT Guide)

| Code | Description |
|------|-------------|
| RAC | Right and Capacity not determinable |
| BEN | Beneficiary information incomplete |
| ORC | ORC classification uncertain |
| DUP | Potential duplicate customer record |
| GOV | Government entity collateral issue |
| LNK | Account linkage discrepancy |
| MRG | Merger/acquisition data integration issue |
| TIM | Timing difference (close of business) |
| DAT | Data quality exception |
| ARE | Additional Record Entity file discrepancy |

---

## API Reference

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/report/{system_id}` | Download full compliance report as JSON |
| `GET` | `/api/systems` | List all discovered operational systems |
| `POST` | `/api/run` | Start a new analysis pipeline run |
| `GET` | `/api/runs/{id}` | Get status/results of a specific run |
| `GET` | `/api/controls` | Get the full regulatory control library |
| `POST` | `/api/controls/validate` | Validate controls against latest findings |
| `GET` | `/api/controls/rag-comparison` | Compare RAG coverage vs control library |
| `GET` | `/api/lineage/graph` | Get data lineage graph (nodes + edges) |

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `ws://localhost:8001/ws` | Real-time pipeline streaming (agent status, findings, progress) |

### Example: Start an Analysis

```bash
curl -X POST http://localhost:8001/api/run \
  -H "Content-Type: application/json" \
  -d '{"institution": "Covered Institution", "use_rag": true, "system_id": "legacy_deposit_system"}'
```

### Example: List Systems

```bash
curl http://localhost:8001/api/systems
```

---

## License

Proprietary — Internal Use Only
