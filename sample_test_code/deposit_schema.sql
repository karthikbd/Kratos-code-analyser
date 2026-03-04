-- =============================================================================
-- deposit_schema.sql
-- FDIC 12 CFR Part 370 — Deposit database schema and reporting queries.
--
-- Semantic-label key (IDs are in regulations/fdic_370_controls.json; labels stable)
-- ---------------------------------------------------------------------------------
--   [UNIQUE_ACCOUNT_ID]     every account row carries a stable non-null primary key
--   [DEPOSITOR_AGGREGATION] depositor_id foreign key links accounts → depositor
--   [GOVT_ID_TYPE]          tin column stores SSN / EIN / ITIN type codes
--   [PII_PROTECTION]        TIN/SSN must be stored encrypted, not as plaintext
--   [BALANCE_QUALITY]       balance column precision and NOT NULL constraint
--   [AUDIT_TRAIL]           audit_log table captures every modification with UTC ts
--   [DETERMINATION_LOG]     determination_run table records every insurance run
--   [PRODUCT_CATEGORY]      account_type CHECK constraint enforces DP_Prod_Cat codes
--   [OWNERSHIP_TYPE]        ownership_category CHECK enforces Part 330 categories
--   [DATA_RETENTION]        closed accounts kept ≥ 5 years before purge
--   [COMPLIANCE_EVIDENCE]   retention_years column must be >= 5
--   [INPUT_VALIDATION]      CHECK constraints enforce domain rules at DB layer
--   [REFERENTIAL_INTEGRITY] FK constraints between accounts, depositors, audit_log
--   [EXCEPTION_REPORT]      determination_exception table surfaces failed accounts
--
-- CROSS-FILE LINEAGE
-- ------------------
--   data_layer.py  DataStore.upsert_account()   → INSERT / UPDATE accounts table
--   data_layer.py  DataStore.get_account()       → SELECT accounts WHERE account_id
--   data_layer.py  AuditLogger.log_modification()→ INSERT audit_log
--   data_layer.py  AuditLogger.record_determination() → INSERT determination_run
--   deposit_service.py  DepositService.reconcile_balances() → reads accounts + gl_balance
--
-- Controls correctly implemented (PASS)
-- ----------------------------------------
--   [UNIQUE_ACCOUNT_ID]     accounts.account_id  PRIMARY KEY NOT NULL
--   [PRODUCT_CATEGORY]      account_type         CHECK against DP_Prod_Cat codes
--   [BALANCE_QUALITY]       balance              NUMERIC(15,2) NOT NULL CHECK >= 0
--   [AUDIT_TRAIL]           audit_log.ts         DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))  (UTC)
--   [DETERMINATION_LOG]     determination_run    table present and NOT NULL on run_id
--   [REFERENTIAL_INTEGRITY] audit_log.account_id REFERENCES accounts(account_id)
--   [EXCEPTION_REPORT]      determination_exception table captures every failed account
--
-- Intentional violations for Kratos to detect
-- -----------------------------------------------
--   CRITICAL  [PII_PROTECTION]        tin column is VARCHAR — stored as raw plaintext
--   HIGH      [OWNERSHIP_TYPE]        ownership_category CHECK omits 'government'
--                                     and 'employee_benefit_plan'
--   HIGH      [DATA_RETENTION]        policy_settings.retention_years default = 3
--                                     (must be >= 5 per 370.4(e))
--   MEDIUM    [DETERMINATION_LOG]     determination_run has no UNIQUE constraint on
--                                     run_id — duplicate run records possible
--   MEDIUM    [AUDIT_TRAIL]           audit_log has no trigger preventing UPDATE/DELETE
--                                     — records are mutable after insert
-- =============================================================================


-- ---------------------------------------------------------------------------
-- 1. Depositor master  [UNIQUE_ACCOUNT_ID] [DEPOSITOR_AGGREGATION]
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS depositors (
    depositor_id   TEXT        PRIMARY KEY NOT NULL,   -- [UNIQUE_ACCOUNT_ID] PASS: stable PK
    full_name      TEXT        NOT NULL,
    -- [PII_PROTECTION] VIOLATION: tin stored as raw plaintext VARCHAR
    tin            TEXT        NOT NULL,               -- VIOLATION [PII_PROTECTION]: should be encrypted blob
    created_at     TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);


-- ---------------------------------------------------------------------------
-- 2. Accounts  [UNIQUE_ACCOUNT_ID] [PRODUCT_CATEGORY] [OWNERSHIP_TYPE] [BALANCE_QUALITY]
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS accounts (
    account_id         TEXT        PRIMARY KEY NOT NULL,  -- [UNIQUE_ACCOUNT_ID] PASS
    depositor_id       TEXT        NOT NULL,              -- [DEPOSITOR_AGGREGATION] PASS: FK to depositors
    -- [PRODUCT_CATEGORY] PASS: only valid DP_Prod_Cat codes accepted
    account_type       TEXT        NOT NULL
        CHECK (account_type IN ('checking','savings','cd','ira','money_market','trust')),
    -- [OWNERSHIP_TYPE] VIOLATION: 'government' and 'employee_benefit_plan' omitted
    ownership_category TEXT        NOT NULL DEFAULT 'single'
        CHECK (ownership_category IN (
            'single','joint','revocable_trust','irrevocable_trust',
            'retirement','business_entity'
            -- MISSING: 'government'              → [OWNERSHIP_TYPE] VIOLATION
            -- MISSING: 'employee_benefit_plan'    → [OWNERSHIP_TYPE] VIOLATION
        )),
    -- [BALANCE_QUALITY] PASS: non-negative numeric precision enforced at DB layer
    balance            NUMERIC(15,2) NOT NULL CHECK (balance >= 0),
    open_date          TEXT        NOT NULL,
    close_date         TEXT,                             -- nullable: [NULL_HANDLING] PASS
    address            TEXT,                             -- optional: [NULL_HANDLING] PASS
    -- [PII_PROTECTION] VIOLATION: tin plaintext duplicated here from depositors row
    tin_cache          TEXT,                             -- VIOLATION [PII_PROTECTION]

    FOREIGN KEY (depositor_id) REFERENCES depositors(depositor_id)  -- [REFERENTIAL_INTEGRITY] PASS
);


-- ---------------------------------------------------------------------------
-- 3. Audit log  [AUDIT_TRAIL] [ACCESS_CONTROL]
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    log_id      TEXT    PRIMARY KEY NOT NULL DEFAULT (lower(hex(randomblob(16)))),
    event_type  TEXT    NOT NULL,       -- 'modification' | 'access' | 'auth'
    actor       TEXT    NOT NULL,       -- user_id performing the action
    account_id  TEXT,                   -- may be NULL for auth events
    field_name  TEXT,
    old_value   TEXT,
    new_value   TEXT,
    -- [AUDIT_TRAIL] PASS: UTC timestamp auto-set by DB; application also sets this
    ts          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),

    FOREIGN KEY (account_id) REFERENCES accounts(account_id)  -- [REFERENTIAL_INTEGRITY] PASS
    -- [AUDIT_TRAIL] VIOLATION: no trigger blocks UPDATE/DELETE — rows are mutable
    -- In production: CREATE TRIGGER prevent_audit_update BEFORE UPDATE ON audit_log ...
);


-- ---------------------------------------------------------------------------
-- 4. Insurance determination run  [DETERMINATION_LOG] [COMPLIANCE_EVIDENCE]
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS determination_run (
    -- [DETERMINATION_LOG] VIOLATION: no UNIQUE constraint — duplicate run_ids possible
    run_id          TEXT    NOT NULL,   -- VIOLATION: should be PRIMARY KEY
    run_type        TEXT    NOT NULL CHECK (run_type IN ('batch','on-demand')),
    depositor_scope TEXT,
    input_json      TEXT,
    result_json     TEXT,
    started_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    completed_at    TEXT
);


-- ---------------------------------------------------------------------------
-- 5. Determination exceptions  [EXCEPTION_REPORT]
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS determination_exception (
    exception_id  TEXT  PRIMARY KEY NOT NULL DEFAULT (lower(hex(randomblob(16)))),
    run_id        TEXT  NOT NULL,
    account_id    TEXT  NOT NULL,
    error_message TEXT  NOT NULL,
    recorded_at   TEXT  NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    -- [EXCEPTION_REPORT] PASS: every failed account gets its own exception row
    FOREIGN KEY (run_id)    REFERENCES determination_run(run_id),   -- [REFERENTIAL_INTEGRITY]
    FOREIGN KEY (account_id) REFERENCES accounts(account_id)        -- [REFERENTIAL_INTEGRITY]
);


-- ---------------------------------------------------------------------------
-- 6. Policy settings  [DATA_RETENTION] [COMPLIANCE_EVIDENCE]
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS policy_settings (
    key    TEXT PRIMARY KEY NOT NULL,
    value  TEXT NOT NULL
);

-- [DATA_RETENTION] VIOLATION: retention_years = 3 (must be >= 5 per 370.4(e))
INSERT OR IGNORE INTO policy_settings (key, value) VALUES
    ('retention_years',       '3'),    -- VIOLATION [DATA_RETENTION]: should be '5'
    ('audit_retention_years', '5');    -- [COMPLIANCE_EVIDENCE] PASS: audit logs kept 5 years


-- ---------------------------------------------------------------------------
-- Reporting queries
-- ---------------------------------------------------------------------------

-- [INSURANCE_CALC] — insured vs uninsured per account (SMDIA = 250,000)
-- Used by: deposit_service.py DepositService.reconcile_balances()
CREATE VIEW IF NOT EXISTS v_insurance_summary AS
SELECT
    a.account_id,
    a.depositor_id,
    a.balance,
    -- [BALANCE_QUALITY] PASS: correct 250,000 SMDIA cap in view
    MIN(a.balance, 250000.00)               AS insured_amount,
    MAX(0.00, a.balance - 250000.00)        AS uninsured_amount,
    a.account_type,
    a.ownership_category
FROM accounts a
WHERE a.close_date IS NULL;   -- active accounts only


-- [DEPOSITOR_AGGREGATION] — aggregate insured total per depositor
-- Used by: business_logic.py InsuranceDeterminationService.per_depositor_summary()
CREATE VIEW IF NOT EXISTS v_depositor_totals AS
SELECT
    a.depositor_id,
    d.full_name,
    COUNT(a.account_id)                         AS account_count,
    SUM(a.balance)                              AS total_balance,
    SUM(MIN(a.balance, 250000.00))              AS total_insured,
    SUM(MAX(0.00, a.balance - 250000.00))       AS total_uninsured
FROM accounts a
JOIN depositors d ON d.depositor_id = a.depositor_id
WHERE a.close_date IS NULL
GROUP BY a.depositor_id, d.full_name;


-- [EXCEPTION_REPORT] — accounts with no determination result in latest run
-- Used by: business_logic.py InsuranceDeterminationService.exception_report()
CREATE VIEW IF NOT EXISTS v_undetermined_accounts AS
SELECT a.account_id, a.depositor_id, a.balance
FROM accounts a
WHERE a.account_id NOT IN (
    SELECT DISTINCT json_extract(value, '$.account_id')
    FROM determination_run dr, json_each(dr.result_json)
    WHERE dr.run_type = 'batch'
);


-- [DATA_RETENTION] — closed accounts eligible for archival purge
-- Archive BEFORE delete — used by: data_layer.py DataStore.purge_closed_accounts()
CREATE VIEW IF NOT EXISTS v_purgeable_accounts AS
SELECT account_id, depositor_id, close_date
FROM accounts
WHERE close_date IS NOT NULL
  AND close_date < date('now', '-' ||
        (SELECT value FROM policy_settings WHERE key = 'retention_years') || ' years');
-- [DATA_RETENTION] VIOLATION: retention_years = 3 means accounts purged after 3 years,
-- not the required 5 — this view returns rows that should still be retained.
