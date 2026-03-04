"""
Data Layer — Database operations, audit logging, and data retention.

Semantic-label key (IDs are in regulations/fdic_370_controls.json; labels here are stable)
-------------------------------------------------------------------------------------------
  [AUDIT_TRAIL]        UTC-timestamped modification log; naive datetime is a violation
  [DETERMINATION_LOG]  append-only record of every insurance determination run
  [ACCESS_CONTROL]     read/write access log for every deposit record operation
  [COMPLIANCE_EVIDENCE] data retention duration (5-year minimum per regulation)
  [DATA_RETENTION]     closed-account archival, purge policy, and retention enforcement
  [PII_PROTECTION]     encryption/masking of SSN and TIN before storage
  [INPUT_VALIDATION]   parameterised queries; pre-flight validation before writes

Controls correctly implemented (PASS)
--------------------------------------
  [AUDIT_TRAIL]        log_modification() uses datetime.now(tz=timezone.utc) — correct UTC
  [DETERMINATION_LOG]  record_determination() persists run_id, inputs, and results
  [ACCESS_CONTROL]     log_access() records user, account, operation on every access
  [INPUT_VALIDATION]   all DataStore queries use parameterised SQL (no f-string injection)
  [COMPLIANCE_EVIDENCE] AUDIT_LOG_RETENTION_YEARS = 5 (correct)

Intentional violations for Kratos to detect
--------------------------------------------
  HIGH   [DETERMINATION_LOG] AuditLogger._log is a plain in-memory list — not backed
                              by a write-protected / append-only persistent store.
  HIGH   [COMPLIANCE_EVIDENCE] RETENTION_YEARS = 3  (must be >= 5 per 370.4(e))
  MEDIUM [AUDIT_TRAIL]         log_access() calls datetime.now() without UTC timezone —
                              timestamp accuracy is unreliable.
  MEDIUM [PII_PROTECTION]      DataStore stores raw TIN/SSN strings with no encryption.
"""
from __future__ import annotations

import sqlite3
import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── [COMPLIANCE_EVIDENCE] / [DATA_RETENTION]: Data retention constants ───────────────────────
# [COMPLIANCE_EVIDENCE] VIOLATION: Must be >= 5 years per 370.4(e).  Value below is wrong.
RETENTION_YEARS: int = 3            # VIOLATION [COMPLIANCE_EVIDENCE] — should be 5
# Correct: RETENTION_YEARS: int = 5  # 12 CFR 370.4(e)

AUDIT_LOG_RETENTION_YEARS: int = 5  # [COMPLIANCE_EVIDENCE]: audit logs kept for 5 years


# ── [AUDIT_TRAIL], [DETERMINATION_LOG], [ACCESS_CONTROL] (Audit logger) ─────────────────────

class AuditLogger:
    """Append-only audit trail for deposit record operations.

    [AUDIT_TRAIL]  log_modification()     — records user, timestamp, old/new values
    [ACCESS_CONTROL]  log_access()           — logs read/write access to deposit records
    [DETERMINATION_LOG]  record_determination() — logs insurance run inputs and results
    [AUDIT_TRAIL]  timestamp accuracy     — [AUDIT_TRAIL] VIOLATION: log_access() uses
                                           datetime.now() without UTC tz (unreliable)
    [DETERMINATION_LOG]  immutability           — [DETERMINATION_LOG] VIOLATION: in-memory list only, not
                                           a write-protected persistent store
    [COMPLIANCE_EVIDENCE]  retention              — AUDIT_LOG_RETENTION_YEARS = 5 (correct)
    """

    def __init__(self) -> None:
        # [DETERMINATION_LOG] VIOLATION: plain list is mutable — should be append-only DB table
        self._log: List[Dict] = []

    def log_modification(
        self,
        user: str,
        account_id: str,
        field: str,
        old_value: Any,
        new_value: Any,
    ) -> None:
        """[AUDIT_TRAIL] — Record data modification with user, timestamp, before/after values."""
        entry = {
            "event": "modification",
            "user": user,
            "account_id": account_id,
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),  # [AUDIT_TRAIL]: UTC
        }
        self._log.append(entry)  # [DETERMINATION_LOG] VIOLATION: mutable list
        logger.info("[AUDIT_TRAIL]: modification logged for account %s field %s", account_id, field)

    def log_access(self, user: str, account_id: str, operation: str) -> None:
        """[ACCESS_CONTROL] — Log read/write access to deposit records.

        [AUDIT_TRAIL] VIOLATION: datetime.now() without timezone — clock unreliable.
        """
        entry = {
            "event": "access",
            "user": user,
            "account_id": account_id,
            "operation": operation,
            "timestamp": datetime.now().isoformat(),  # [AUDIT_TRAIL] VIOLATION: no tz
        }
        self._log.append(entry)
        logger.info("[ACCESS_CONTROL]: access logged for account %s op=%s", account_id, operation)

    def record_determination(
        self,
        run_id: str,
        depositor_id: str,
        inputs: Dict,
        results: Dict,
    ) -> None:
        """[DETERMINATION_LOG] — Log each insurance determination run with inputs and results."""
        entry = {
            "event": "determination",
            "run_id": run_id,
            "depositor_id": depositor_id,
            "inputs": inputs,
            "results": results,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
        self._log.append(entry)  # [DETERMINATION_LOG] VIOLATION: mutable list, no immutability guarantee
        logger.info("[DETERMINATION_LOG]: determination run %s logged for depositor %s", run_id, depositor_id)

    def get_log(self) -> List[Dict]:
        """[COMPLIANCE_EVIDENCE] — Expose log for retention management (caller enforces AUDIT_LOG_RETENTION_YEARS)."""
        return list(self._log)


audit_logger = AuditLogger()


# ── [PII_PROTECTION] / [INPUT_VALIDATION]: DataStore (deposit record persistence) ───────────

class DataStore:
    """SQLite-backed deposit record store.

    [INPUT_VALIDATION]: All queries use parameterised statements (? placeholders).
    [PII_PROTECTION] VIOLATION: TIN/SSN stored as raw plaintext strings — PII not
                      encrypted at rest.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        """Establish database connection."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self._init_schema()
            logger.info("DataStore connected: %s", self.db_path)
        except Exception as exc:
            logger.error("DB connection failed: %s", exc)

    def _init_schema(self) -> None:
        """Create deposit tables if they do not exist."""
        assert self.conn is not None
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS accounts (
                account_id      TEXT PRIMARY KEY,
                depositor_name  TEXT NOT NULL,
                tin             TEXT,        -- [PII_PROTECTION] VIOLATION: stored plaintext
                account_type    TEXT,
                balance         REAL,
                ownership_cat   TEXT,
                open_date       TEXT,
                close_date      TEXT,
                address         TEXT
            );
            CREATE TABLE IF NOT EXISTS users (
                id   TEXT PRIMARY KEY,
                name TEXT
            );
            CREATE TABLE IF NOT EXISTS audit_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                event     TEXT,
                payload   TEXT,
                logged_at TEXT
            );
        """)
        self.conn.commit()

    # ─ Deposit record operations ([UNIQUE_ACCOUNT_ID], [PRODUCT_CATEGORY], [INPUT_VALIDATION]) ────────

    def get_account(self, account_id: str) -> Optional[Dict]:
        """[INPUT_VALIDATION]: parameterised query — no f-string concatenation."""
        try:
            assert self.conn is not None
            cur = self.conn.execute(
                "SELECT * FROM accounts WHERE account_id = ?",
                (account_id,),          # [INPUT_VALIDATION]: parameterised
            )
            row = cur.fetchone()
            if row:
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))
            return None
        except Exception as exc:
            logger.error("get_account failed for %s: %s", account_id, exc)
            return None

    def upsert_account(self, record: Dict) -> bool:
        """Persist or update an account record ([UNIQUE_ACCOUNT_ID] unique key, [PRODUCT_CATEGORY] type codes)."""
        try:
            assert self.conn is not None
            self.conn.execute(
                """
                INSERT INTO accounts
                    (account_id, depositor_name, tin, account_type, balance,
                     ownership_cat, open_date, close_date, address)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(account_id) DO UPDATE SET
                    depositor_name=excluded.depositor_name,
                    tin=excluded.tin,
                    balance=excluded.balance,
                    close_date=excluded.close_date
                """,
                (
                    record.get("account_id"),
                    record.get("depositor_name"),
                    record.get("tin"),             # [PII_PROTECTION] VIOLATION: raw TIN
                    record.get("account_type"),
                    record.get("balance"),
                    record.get("ownership_cat"),
                    record.get("open_date"),
                    record.get("close_date"),
                    record.get("address"),
                ),
            )
            self.conn.commit()
            return True
        except Exception as exc:
            logger.error("upsert_account failed: %s", exc)
            return False

    # ─ [COMPLIANCE_EVIDENCE] / [DATA_RETENTION]: Data retention ──────────────────────────

    def archive_closed_accounts(self, as_of: date) -> int:
        """[DATA_RETENTION] / [COMPLIANCE_EVIDENCE] — Archive accounts closed beyond the retention window.

        [COMPLIANCE_EVIDENCE] VIOLATION: uses RETENTION_YEARS = 3 instead of required 5.
        [DATA_RETENTION]: closed account records preserved in archive before deletion.
        [DATA_RETENTION]: automated archival process — caller wires to a scheduler.
        """
        cutoff_year = as_of.year - RETENTION_YEARS  # [COMPLIANCE_EVIDENCE] VIOLATION
        cutoff = date(cutoff_year, as_of.month, as_of.day).isoformat()
        assert self.conn is not None
        cur = self.conn.execute(
            "SELECT * FROM accounts WHERE close_date IS NOT NULL AND close_date < ?",
            (cutoff,),  # [INPUT_VALIDATION]: parameterised
        )
        rows = cur.fetchall()
        archived = 0
        for row in rows:
            # [DATA_RETENTION]: in a real system this would INSERT into an archive table / blob store
            logger.info("[DATA_RETENTION]: archiving closed account %s (closed %s)", row[0], row[7])
            archived += 1
        logger.info("[DATA_RETENTION]: archived %d accounts closed before %s", archived, cutoff)
        return archived

    def purge_expired_determination_records(self, as_of: date) -> int:
        """[DATA_RETENTION] — Purge insurance determination outputs beyond retention window."""
        cutoff_year = as_of.year - RETENTION_YEARS  # [COMPLIANCE_EVIDENCE] VIOLATION propagates
        cutoff = date(cutoff_year, as_of.month, as_of.day).isoformat()
        assert self.conn is not None
        cur = self.conn.execute(
            "DELETE FROM audit_log WHERE event = 'determination' AND logged_at < ?",
            (cutoff,),
        )
        self.conn.commit()
        logger.info("[DATA_RETENTION]: purged %d determination records before %s", cur.rowcount, cutoff)
        return cur.rowcount

    # ─ User table helpers (used by auth flow) ──────────────────────────────

    def get_user(self, user_id: str) -> Optional[Dict]:
        """[INPUT_VALIDATION]: parameterised query."""
        try:
            assert self.conn is not None
            cur = self.conn.execute("SELECT id, name FROM users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            return {"id": row[0], "name": row[1]} if row else None
        except Exception as exc:
            logger.error("get_user failed: %s", exc)
            return None

    def create_user(self, user_id: str, name: str) -> bool:
        """[INPUT_VALIDATION]: parameterised INSERT."""
        try:
            assert self.conn is not None
            self.conn.execute(
                "INSERT INTO users (id, name) VALUES (?, ?)", (user_id, name)
            )
            self.conn.commit()
            logger.info("User %s created", user_id)
            return True
        except Exception as exc:
            logger.error("create_user failed: %s", exc)
            return False
