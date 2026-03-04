import ast
import re
from typing import Dict, Any


ENCRYPTION_KEYWORDS = {"cryptography", "fernet", "aes", "rsa", "bcrypt", "argon2", "hashlib", "hmac", "ssl"}
AUTH_KEYWORDS = {"jwt", "oauth", "auth", "login", "token", "authenticate", "authorize"}
DB_KEYWORDS = {"sqlalchemy", "psycopg2", "pymysql", "sqlite3", "cursor", "session", "orm", "models"}
LOG_KEYWORDS = {"logging", "logger", "log", "audit"}


def ast_summary(source_code: str, language: str) -> Dict[str, Any]:
    summary = {
        "lines": len(source_code.splitlines()),
        "functions": [],
        "classes": [],
        "imports": [],
        "has_encryption": False,
        "has_logging": False,
        "has_auth": False,
        "has_db": False,
        "has_error_handling": False,
    }

    if language != "python":
        summary["functions"] = re.findall(
            r"(?:def|function|func|void|public|private)\s+(\w+)\s*\(", source_code
        )[:40]
        summary["classes"] = re.findall(
            r"(?:class|interface|struct)\s+(\w+)", source_code
        )[:20]
        text = source_code.lower()
        summary["has_encryption"] = any(k in text for k in ENCRYPTION_KEYWORDS)
        summary["has_logging"] = any(k in text for k in LOG_KEYWORDS)
        summary["has_auth"] = any(k in text for k in AUTH_KEYWORDS)
        summary["has_db"] = any(k in text for k in DB_KEYWORDS)
        summary["has_error_handling"] = bool(
            re.search(r"(try\s*{|catch\s*\(|except\s|rescue\s)", source_code)
        )
        return summary

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return summary

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            summary["functions"].append(node.name)
        elif isinstance(node, ast.ClassDef):
            summary["classes"].append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                summary["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            summary["imports"].append(node.module)
        elif isinstance(node, ast.ExceptHandler):
            summary["has_error_handling"] = True

    imports_text = " ".join(summary["imports"]).lower()
    text = source_code.lower()
    summary["has_encryption"] = any(k in imports_text or k in text for k in ENCRYPTION_KEYWORDS)
    summary["has_logging"] = any(k in imports_text or k in text for k in LOG_KEYWORDS)
    summary["has_auth"] = any(k in imports_text or k in text for k in AUTH_KEYWORDS)
    summary["has_db"] = any(k in imports_text or k in text for k in DB_KEYWORDS)

    summary["functions"] = list(dict.fromkeys(summary["functions"]))[:40]
    summary["classes"] = list(dict.fromkeys(summary["classes"]))[:20]
    summary["imports"] = list(dict.fromkeys(summary["imports"]))[:40]
    return summary


def heuristic_signals(source_code: str) -> Dict[str, Any]:
    lines = source_code.splitlines()
    signals = {
        "hardcoded_secrets_lines": [],
        "raw_sql_lines": [],
        "external_http_lines": [],
    }
    secret_re = re.compile(r"(password|secret|api_key|token)\s*=\s*['\"]", re.I)
    sql_re = re.compile(r"(SELECT|INSERT|UPDATE|DELETE).*\+", re.I)
    http_re = re.compile(r"requests\.(get|post|put|delete)\(", re.I)

    for i, line in enumerate(lines, start=1):
        if secret_re.search(line):
            signals["hardcoded_secrets_lines"].append((i, line.strip()))
        if sql_re.search(line):
            signals["raw_sql_lines"].append((i, line.strip()))
        if http_re.search(line):
            signals["external_http_lines"].append((i, line.strip()))

    return signals


def build_lineage(sources: Dict[str, str]) -> list:
    """
    Build a simple cross-file lineage graph using imports and dotted-name uses.
    Returns a list of edges: {source_file, target_file, type, evidence}
    """
    edges = []

    # map module base name -> filename
    module_map = {}
    for fname in sources.keys():
        base = fname.rsplit("/", 1)[-1]
        name = base.split(".", 1)[0]
        module_map[name] = fname

    import_re = re.compile(r"^\s*(?:from|import)\s+([\w\.]+)", re.M)
    dotted_re = re.compile(r"(\b[\w_]+)\.")

    for fname, src in sources.items():
        found = set()
        for m in import_re.findall(src):
            top = m.split(".")[0]
            if top in module_map and module_map[top] != fname:
                edge = {
                    "source_file": fname,
                    "target_file": module_map[top],
                    "type": "import",
                    "evidence": m,
                }
                if (fname, module_map[top], "import") not in found:
                    edges.append(edge)
                    found.add((fname, module_map[top], "import"))

        for m in dotted_re.findall(src):
            if m in module_map and module_map[m] != fname:
                edge = {
                    "source_file": fname,
                    "target_file": module_map[m],
                    "type": "dotted_use",
                    "evidence": m,
                }
                if (fname, module_map[m], "dotted_use") not in found:
                    edges.append(edge)
                    found.add((fname, module_map[m], "dotted_use"))

    return edges


def detect_missing_controls_for_sources(sources: Dict[str, str]) -> Dict[str, list]:
    """
    Heuristically detect likely-missing controls per file using `ast_summary`.
    Returns mapping filename -> list of missing control keywords.
    """
    missing = {}
    for fname, src in sources.items():
        s = ast_summary(src, "python")
        miss = []
        if not s.get("has_logging"):
            miss.append("audit_log")
        if not s.get("has_error_handling"):
            miss.append("error_handling")
        if not s.get("has_auth"):
            miss.append("authentication/authorization")
        if not s.get("has_encryption"):
            miss.append("encryption_usage_detected")
        missing[fname] = miss
    return missing
