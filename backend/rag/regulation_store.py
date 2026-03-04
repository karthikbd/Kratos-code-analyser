"""
RAG store for FDIC Part 370 controls.

Knowledge-source priority:
  1. regulations/fdic_370_controls.json  – structured, pre-extracted controls (preferred)
  2. regulations/fdic_370_online.txt     – raw text fetched from eCFR / FDIC.gov (fallback)

Arbitrary .txt files in the regulations/ folder are deliberately NOT loaded.
"""
import json as _json
import logging
import os
import re as _re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import httpx
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from backend.config import settings

log = logging.getLogger(__name__)

# ── Filenames ──────────────────────────────────────────────────────────────────
JSON_FILENAME = "fdic_370_controls.json"
FALLBACK_TXT = "fdic_370_online.txt"

# ── Official FDIC / eCFR sources (tried in order if JSON is absent) ────────────
_ONLINE_SOURCES = [
    # eCFR provides clean plain-HTML for 12 CFR Part 370
    "https://www.ecfr.gov/current/title-12/chapter-II/subchapter-B/part-370",
    # FDIC informational page
    "https://www.fdic.gov/banker-resource-center/12-cfr-part-370-recordkeeping-"
    "timely-deposit-insurance-determination",
]


# ── Path helpers ───────────────────────────────────────────────────────────────

def _reg_dir() -> str:
    base = settings.REGULATIONS_DIR
    if not os.path.isabs(base):
        base = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "..", "regulations"
        )
    os.makedirs(base, exist_ok=True)
    return os.path.abspath(base)


def _json_path() -> Path:
    return Path(_reg_dir()) / JSON_FILENAME


def _fallback_txt_path() -> Path:
    return Path(_reg_dir()) / FALLBACK_TXT


# ── JSON → Documents ───────────────────────────────────────────────────────────

def _load_json_control_docs(json_path: Path) -> List[Document]:
    """Convert every requirement in fdic_370_controls.json into a LangChain Document.

    Each requirement becomes one Document so agents can retrieve individual
    controls by semantic similarity.  Metadata preserves requirement_id,
    rule_type, applicable_fields, and source_location for downstream filtering.
    """
    try:
        with json_path.open(encoding="utf-8") as fh:
            data = _json.load(fh)
    except Exception as exc:
        raise RuntimeError(f"Failed to parse {json_path}: {exc}") from exc

    docs: List[Document] = []
    for req in data.get("requirements", []):
        req_id = req.get("requirement_id", "UNKNOWN")
        rule_type = req.get("rule_type", "")
        description = req.get("rule_description", "")
        source_loc = req.get("metadata", {}).get("source_location", "FDIC 370")
        applicable = ", ".join(req.get("applicable_fields") or [])
        control_obj = req.get("control_objective", "")
        first_sentence = description.split(".")[0].strip()
        title = first_sentence[:120] if first_sentence else req_id

        page_content = (
            f"FDIC 370 Control [{req_id}] ({source_loc})\n"
            f"Category: {rule_type}\n"
            f"Objective: {control_obj}\n"
            f"Title: {title}\n"
            f"Description: {description}"
        )
        if applicable:
            page_content += f"\nApplicable Fields: {applicable}"

        docs.append(
            Document(
                page_content=page_content,
                metadata={
                    "requirement_id": req_id,
                    "rule_type": rule_type,
                    "source_location": source_loc,
                    "source_file": JSON_FILENAME,
                },
            )
        )

    log.info("Loaded %d FDIC 370 controls from %s.", len(docs), JSON_FILENAME)
    return docs


# ── Online fallback ────────────────────────────────────────────────────────────

def _strip_html(html: str) -> str:
    html = _re.sub(r"<script.*?</script>", " ", html, flags=_re.S | _re.I)
    html = _re.sub(r"<style.*?</style>", " ", html, flags=_re.S | _re.I)
    html = _re.sub(r"<[^>]+>", " ", html)
    html = _re.sub(r"\s{3,}", "\n\n", html)
    return html.strip()


def _fetch_fdic_online() -> str:
    """Try each URL in _ONLINE_SOURCES and return the first usable text."""
    for url in _ONLINE_SOURCES:
        try:
            log.info("Fetching FDIC Part 370 text from %s …", url)
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                r = client.get(url)
                r.raise_for_status()
                content_type = r.headers.get("content-type", "")
                text = _strip_html(r.text) if "html" in content_type.lower() else r.text
                if len(text) > 5000:
                    return text
        except Exception as exc:
            log.warning("Could not fetch %s: %s", url, exc)
    return ""


def _fallback_text_docs(txt_path: Path) -> List[Document]:
    """Wrap saved online FDIC text in a Document list for embedding."""
    try:
        text = txt_path.read_text(encoding="utf-8")
    except Exception:
        return []
    return [
        Document(
            page_content=text,
            metadata={"source_file": FALLBACK_TXT, "source": "FDIC online"},
        )
    ]


# ── Startup guard ──────────────────────────────────────────────────────────────

async def ensure_regulations_ready():
    """
    Verify that at least one regulation source is ready before the server
    starts accepting requests.

    Decision tree
    ─────────────
    1. fdic_370_controls.json present → perfect, nothing to do.
    2. JSON absent, fdic_370_online.txt present (cached) → reuse it.
    3. Both absent → fetch FDIC Part 370 text from eCFR / FDIC.gov.
    4. Fetch also fails → raise RuntimeError with clear remediation steps.
    """
    json_p = _json_path()

    if json_p.exists():
        log.info("✓ %s found – RAG will be built from structured JSON.", JSON_FILENAME)
        return

    log.warning(
        "⚠  %s not found in %s.\n"
        "   Attempting to fetch FDIC Part 370 regulation text online …",
        JSON_FILENAME,
        _reg_dir(),
    )

    txt_p = _fallback_txt_path()
    if txt_p.exists() and txt_p.stat().st_size > 5000:
        log.info("Reusing cached online FDIC text at %s.", txt_p.name)
        return

    text = _fetch_fdic_online()
    if text:
        txt_p.write_text(text, encoding="utf-8")
        log.info(
            "✓ Downloaded FDIC Part 370 text (%d chars) → saved as %s.",
            len(text),
            txt_p.name,
        )
        return

    raise RuntimeError(
        "\n\n"
        f"❌  '{JSON_FILENAME}' was not found in {_reg_dir()!r} and the online "
        "fetch from eCFR / FDIC.gov also failed.\n\n"
        "Please do ONE of the following and restart the server:\n"
        f"  1. Place '{JSON_FILENAME}' in the regulations/ folder.  ← preferred\n"
        "  2. Check your internet connection (eCFR and FDIC.gov must be reachable).\n"
        f"  3. Manually save FDIC Part 370 full text to:\n"
        f"       {txt_p}\n"
    )


# ── Core document loader ───────────────────────────────────────────────────────

def _load_docs() -> List[Document]:
    """
    Return Documents for embedding.

    Source selection (in priority order):
      1. fdic_370_controls.json  – structured JSON extracted from the regulation
      2. fdic_370_online.txt     – raw text fetched from eCFR / FDIC.gov

    No arbitrary .txt files are loaded; only the two filenames above are
    ever accessed.
    """
    json_p = _json_path()
    if json_p.exists():
        return _load_json_control_docs(json_p)

    txt_p = _fallback_txt_path()
    if txt_p.exists() and txt_p.stat().st_size > 5000:
        log.warning(
            "Using online-text fallback (%s). "
            "Provide '%s' for higher-quality retrieval.",
            txt_p.name,
            JSON_FILENAME,
        )
        return _fallback_text_docs(txt_p)

    raise RuntimeError(
        "No regulation source available. "
        f"Provide '{JSON_FILENAME}' in regulations/ or ensure ensure_regulations_ready() "
        "has run successfully to download the online fallback."
    )


@lru_cache(maxsize=1)
def get_vector_store() -> FAISS:
    """
    Build a FAISS store from regulation docs, staying far below OpenAI's
    300k max_tokens_per_request limit for embeddings.
    """
    documents = _load_docs()

    # 1) Very hard cap on total characters (approx tokens / 4).
    MAX_CHARS = 300_000  # ~75k tokens
    cur = 0
    trimmed_docs = []
    for d in documents:
        if cur >= MAX_CHARS:
            break
        text = d.page_content
        remaining = MAX_CHARS - cur
        if len(text) > remaining:
            d.page_content = text[:remaining]
            trimmed_docs.append(d)
            cur = MAX_CHARS
            break
        trimmed_docs.append(d)
        cur += len(text)

    # 2) Small chunks to keep per‑chunk tokens low.
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
    )
    chunks = splitter.split_documents(trimmed_docs)

    # 3) Cap number of chunks embedded in one call.
    MAX_CHUNKS = 800
    chunks = chunks[:MAX_CHUNKS]

    embeddings = OpenAIEmbeddings(model=settings.EMBEDDING_MODEL)

    try:
        return FAISS.from_documents(chunks, embeddings)
    except Exception:
        # Safety fallback: embed only a smaller subset if we still somehow exceed limits.
        fallback_chunks = chunks[:200]
        return FAISS.from_documents(fallback_chunks, embeddings)


def retrieve_regulation_chunks(query: str, k: int = 10) -> List[str]:
    vectordb = get_vector_store()
    docs = vectordb.similarity_search(query, k=k)
    return [d.page_content for d in docs]


def retrieve_controls_with_metadata(query: str, k: int = 10) -> List[Dict[str, Any]]:
    """Semantic search that returns chunk text plus full metadata.

    Agents use this to retrieve the most relevant FDIC 370 controls for a
    specific code signal (e.g. 'insurance aggregation SMDIA 250000') and
    get back structured data including requirement_id so they can cross-
    reference findings with the control library.
    """
    vectordb = get_vector_store()
    results = vectordb.similarity_search_with_score(query, k=k)
    return [
        {
            "content": doc.page_content,
            "metadata": doc.metadata,
            "score": float(score),
        }
        for doc, score in results
    ]
