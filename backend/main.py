import truststore
truststore.inject_into_ssl()

import re
import asyncio
from typing import Optional, Dict, Any, List

import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from backend.config import settings
from backend.rag.regulation_store import ensure_regulations_ready
from backend.agents.graph import analyze_file_agentic
from backend.models.outputs import FileAnalysis, RepoAnalysis


app = FastAPI(title="Kratos Agentic Analyzer", version="3.0.0")
app.mount("/static", StaticFiles(directory="frontend"), name="static")


class AnalyzeTextRequest(BaseModel):
    filename: str
    source_code: str
    language: Optional[str] = "python"


class GithubFileRequest(BaseModel):
    url: str


class GithubRepoRequest(BaseModel):
    repo_url: str


LANG_MAP = {
    "py": "python",
    "js": "javascript",
    "jsx": "javascript",
    "ts": "typescript",
    "tsx": "typescript",
    "java": "java",
    "kt": "kotlin",
    "scala": "scala",
    "c": "c",
    "cpp": "cpp",
    "cs": "csharp",
    "go": "go",
    "rs": "rust",
    "swift": "swift",
    "php": "php",
    "rb": "ruby",
    "sql": "sql",
    "sh": "bash",
    "bash": "bash",
    "zsh": "bash",
    "yaml": "yaml",
    "yml": "yaml",
    "toml": "toml",
    "ini": "ini",
    "cfg": "ini",
    "conf": "ini",
    "env": "ini",
    "html": "html",
    "htm": "html",
    "css": "css",
    "json": "json",
    "xml": "xml",
    "tf": "terraform",
    "hcl": "terraform",
    "md": "markdown",
    "txt": "text",
}
SUPPORTED_EXTS = set(LANG_MAP.keys())
SPECIAL_FILENAMES = {
    "dockerfile": "dockerfile",
    "makefile": "makefile",
    "jenkinsfile": "groovy",
    "vagrantfile": "ruby",
    ".env": "ini",
}

SKIP_DIRS = {
    "node_modules", "vendor", "dist", "build", "target",
    ".git", "migrations", "__pycache__", ".venv", "venv",
    "coverage", ".nyc_output", "tmp", "temp", "logs",
    "bin", "obj", ".gradle", ".mvn", "bower_components",
}
SKIP_FILE_PATTERNS = [
    r'\.min\.(js|css)$',
    r'[-.]bundle\.',
    r'\.lock$',
    r'package-lock\.json$', r'yarn\.lock$',
    r'\.map$',
    r'\.pyc$', r'\.class$', r'\.jar$', r'\.war$',
    r'\.png$|\.jpg$|\.gif$|\.svg$|\.ico$',
    r'\.ttf$|\.woff2?$|\.eot$',
    r'\.pdf$|\.docx?$|\.xlsx?$',
]
MAX_FILE_SIZE_BYTES = 80_000
MAX_CONCURRENT = 6


@app.on_event("startup")
async def startup_event():
    await ensure_regulations_ready()


def github_headers() -> dict:
    h = {"Accept": "application/vnd.github.v3+json"}
    if settings.GITHUB_TOKEN:
        h["Authorization"] = f"token {settings.GITHUB_TOKEN}"
    return h


def detect_language(filename: str) -> str:
    lower = filename.lower()
    if lower in SPECIAL_FILENAMES:
        return SPECIAL_FILENAMES[lower]
    if "." not in lower:
        return "text"
    ext = lower.rsplit(".", 1)[-1]
    return LANG_MAP.get(ext, "text")


def should_skip_file(path: str) -> bool:
    lower = path.lower()
    for pattern in SKIP_FILE_PATTERNS:
        if re.search(pattern, lower):
            return True
    return False


def is_supported_file(item: dict) -> bool:
    if item.get("type") != "blob":
        return False
    path = item.get("path", "")
    filename = path.split("/")[-1].lower()
    parts = path.split("/")
    if any(skip in parts for skip in SKIP_DIRS):
        return False
    if should_skip_file(path):
        return False
    if filename in SPECIAL_FILENAMES:
        return True
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1]
        return ext in SUPPORTED_EXTS
    return False


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    with open("frontend/index.html", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "Kratos Agentic Analyzer"}


@app.post("/api/analyze/text")
async def analyze_text(req: AnalyzeTextRequest):
    if not req.source_code.strip():
        raise HTTPException(400, "source_code is empty")
    result = await analyze_file_agentic(req.filename, req.source_code, req.language or "python")
    return result.model_dump()


@app.post("/api/analyze/file")
async def analyze_file(file: UploadFile = File(...)):
    content = await file.read()
    try:
        source = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "File must be UTF-8 text")
    if not source.strip():
        raise HTTPException(400, "Uploaded file is empty")
    language = detect_language(file.filename or "code.py")
    result = await analyze_file_agentic(file.filename, source, language)
    return result.model_dump()


@app.post("/api/analyze/github/file")
async def analyze_github_file(req: GithubFileRequest):
    url = req.url.strip()
    if "/blob/" not in url:
        raise HTTPException(
            400,
            "Single file URL must contain /blob/ "
            "(e.g. https://github.com/org/repo/blob/main/app.py)",
        )
    raw_url = (
        url.replace("https://github.com/", "https://raw.githubusercontent.com/")
           .replace("/blob/", "/")
    )
    filename = raw_url.split("/")[-1] or "code.py"
    language = detect_language(filename)

    try:
        async with httpx.AsyncClient(timeout=30, verify=False) as client:
            r = await client.get(raw_url, headers=github_headers())
            r.raise_for_status()
    except httpx.RequestError as e:
        raise HTTPException(502, f"GitHub network error: {e}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, f"GitHub error: {e}")

    code = r.text
    if not code.strip():
        raise HTTPException(400, "File is empty")

    result = await analyze_file_agentic(filename, code, language)
    return result.model_dump()


async def _scan_one_file(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    branch: str,
    item: dict,
    semaphore: asyncio.Semaphore,
) -> FileAnalysis | None:
    path = item["path"]
    filename = path.split("/")[-1]
    language = detect_language(filename)
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"

    async with semaphore:
        try:
            r = await client.get(raw_url, headers=github_headers())
            if r.status_code != 200:
                return None
            code = r.text
            if not code.strip():
                return None
            if len(code.encode()) > MAX_FILE_SIZE_BYTES:
                return None
            return await analyze_file_agentic(path, code, language)
        except Exception:
            return None


@app.post("/api/analyze/github/repo")
async def analyze_github_repo(req: GithubRepoRequest):
    repo_url = req.repo_url.strip().rstrip("/")
    if repo_url.endswith(".git"):
        repo_url = repo_url[:-4]

    match = re.search(r"github\.com/([^/]+)/([^/\s]+)", repo_url)
    if not match:
        raise HTTPException(
            400,
            "Invalid GitHub URL. Use https://github.com/owner/repo or /tree/branch",
        )

    owner = match.group(1)
    repo = match.group(2).replace(".git", "")
    api_base = f"https://api.github.com/repos/{owner}/{repo}"

    try:
        async with httpx.AsyncClient(timeout=30, verify=False) as client:
            meta = await client.get(api_base, headers=github_headers())
            if meta.status_code == 404:
                raise HTTPException(404, f"Repo not found: {owner}/{repo}")
            if meta.status_code in (401, 403):
                raise HTTPException(meta.status_code, "GitHub auth/rate limit error")
            meta.raise_for_status()
            default_branch = meta.json().get("default_branch", "main")

            tree_r = await client.get(
                f"{api_base}/git/trees/{default_branch}?recursive=1",
                headers=github_headers(),
            )
            tree_r.raise_for_status()
            tree = tree_r.json().get("tree", [])
    except httpx.RequestError as e:
        raise HTTPException(502, f"GitHub API error: {e}")

    files = [item for item in tree if is_supported_file(item)]
    if not files:
        raise HTTPException(404, "No scannable code files found in repo.")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    async with httpx.AsyncClient(timeout=120, verify=False) as client:
        tasks = [
            _scan_one_file(client, owner, repo, default_branch, item, semaphore)
            for item in files
        ]
        results = await asyncio.gather(*tasks)

    per_file: List[FileAnalysis] = [r for r in results if r is not None]
    if not per_file:
        raise HTTPException(500, "All files failed or were skipped.")

    total_loc = sum(f.lines_of_code for f in per_file)
    language_counts: Dict[str, int] = {}
    category_counts: Dict[str, int] = {}
    for f in per_file:
        lang = f.language or "unknown"
        language_counts[lang] = language_counts.get(lang, 0) + 1
        if any(x in f.filename.lower() for x in ["dockerfile", "terraform", ".github/workflows"]):
            cat = "DevOps / CI-CD"
        elif any(x in f.filename.lower() for x in ["migrations", ".sql"]):
            cat = "Database / SQL"
        else:
            cat = "App / Service"
        category_counts[cat] = category_counts.get(cat, 0) + 1

    order = ["Very Low", "Low", "Moderate", "Elevated", "Severe"]
    max_idx = max(order.index(f.qualitative_risk) for f in per_file if f.qualitative_risk in order)
    repo_risk = order[max_idx]

    overall_summary = (
        f"Agentic analysis of {owner}/{repo} on branch {default_branch} "
        f"covered {len(per_file)} files ({total_loc} LOC). "
        f"The highest qualitative risk observed is {repo_risk}. "
        "See per-file narratives for inline control details and regulatory alignment."
    )

    repo_analysis = RepoAnalysis(
        repo=f"{owner}/{repo}",
        branch=default_branch,
        files_analyzed=len(per_file),
        total_loc=total_loc,
        qualitative_risk=repo_risk,
        overall_summary=overall_summary,
        per_file=per_file,
        language_counts=language_counts,
        category_counts=category_counts,
    )
    return repo_analysis.model_dump()
