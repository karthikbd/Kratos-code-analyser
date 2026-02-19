import os
from functools import lru_cache
from typing import List

import httpx
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

from backend.config import settings


FDIC_370_URL = (
    "https://www.fdic.gov/banker-resource-center/12-cfr-part-370-recordkeeping-"
    "timely-deposit-insurance-determination"
)
FDIC_GUIDE_URL = (
    "https://www.fdic.gov/regulations/resources/recordkeeping/documents/"
    "info-tech-func-guide-for-implement-part370.pdf"
)
OWASP_SECURE_CODE_URL = (
    "https://cheatsheetseries.owasp.org/cheatsheets/Secure_Code_Review_Cheat_Sheet.html"
)
NIST_800_53_URL = (
    "https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final"
)


def _reg_dir() -> str:
    base = settings.REGULATIONS_DIR
    if not os.path.isabs(base):
        base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "regulations")
    os.makedirs(base, exist_ok=True)
    return os.path.abspath(base)


async def _download_text(url: str, dest: str):
    if os.path.exists(dest) and os.path.getsize(dest) > 5000:
        return
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            content_type = r.headers.get("content-type", "")
            text = r.text
            if "html" in content_type.lower():
                import re as _re
                text = _re.sub(r"<script.*?</script>", " ", text, flags=_re.S | _re.I)
                text = _re.sub(r"<style.*?</style>", " ", text, flags=_re.S | _re.I)
                text = _re.sub(r"<[^>]+>", " ", text)
            with open(dest, "w", encoding="utf-8") as f:
                f.write(text)
    except Exception:
        return


async def ensure_regulations_ready():
    base = _reg_dir()
    await _download_text(FDIC_370_URL, os.path.join(base, "fdic_370.txt"))
    await _download_text(FDIC_GUIDE_URL, os.path.join(base, "fdic_it_guide.txt"))
    await _download_text(OWASP_SECURE_CODE_URL, os.path.join(base, "owasp_secure_code.txt"))
    await _download_text(NIST_800_53_URL, os.path.join(base, "nist_800_53.txt"))


def _load_docs():
    base = _reg_dir()
    docs = []
    for root, _, files in os.walk(base):
        for name in files:
            path = os.path.join(root, name)
            try:
                loader = TextLoader(path, encoding="utf-8")
                docs.extend(loader.load())
            except Exception:
                continue
    return docs


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
