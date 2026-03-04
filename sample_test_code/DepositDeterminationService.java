package com.pnc.fdic370;

/**
 * DepositDeterminationService.java
 * FDIC 12 CFR Part 370 — Insurance determination and audit service (Java layer).
 *
 * <p>Semantic-label key (IDs are in regulations/fdic_370_controls.json; labels stable)
 * <pre>
 *   [AUDIT_TRAIL]         UTC-timestamped immutable record of every operation
 *   [ACCESS_CONTROL]      JWT validation and RBAC check before any privileged call
 *   [INSURANCE_CALC]      SMDIA cap (250,000) applied per account
 *   [BALANCE_QUALITY]     balance precision and non-negative validation
 *   [DETERMINATION_LOG]   run record written after every batch and on-demand job
 *   [RECONCILIATION]      master reconciliation against GL after each batch pass
 *   [EXCEPTION_REPORT]    failed accounts surfaced in structured exception list
 *   [COMPLIANCE_EVIDENCE] certification artifact existence check
 *   [RECORD_MATCHING]     depositor name matched against govt ID on record
 *   [UNIQUE_ACCOUNT_ID]   stable non-null account identifier enforced
 * </pre>
 *
 * <p><b>CROSS-FILE LINEAGE</b>
 * <pre>
 *   THIS FILE (Java tier)
 *     ↓  REST call
 *   api_endpoints.py  on_demand_determine() / batch_determine()
 *     ↓  delegate
 *   business_logic.py InsuranceDeterminationService.trigger_on_demand()
 *     ↓  reads
 *   data_layer.py     DataStore.get_account()  →  deposit_schema.sql  accounts table
 *     ↓  writes
 *   data_layer.py     AuditLogger.record_determination()  →  determination_run table
 * </pre>
 *
 * <p>The Java service acts as a downstream consumer of the Python REST API.
 * It re-validates auth tokens, applies its own RBAC check, then delegates to
 * the Python backend. Any compliance gap in this layer is independent of the
 * Python layer's gaps — both must pass for end-to-end compliance.
 *
 * <p><b>Controls correctly implemented (PASS)</b>
 * <pre>
 *   [AUDIT_TRAIL]         logEvent() writes actor, timestamp (Instant.now UTC), operation
 *   [ACCESS_CONTROL]      determineOnDemand() calls verifyToken() then checkPermission()
 *   [INSURANCE_CALC]      calculateInsured() caps at 250_000L (correct SMDIA)
 *   [BALANCE_QUALITY]     validateBalance() rejects negative and null balances
 *   [EXCEPTION_REPORT]    runBatch() collects failures into List&lt;BatchError&gt; — none dropped
 * </pre>
 *
 * <p><b>Intentional violations for Kratos to detect</b>
 * <pre>
 *   CRITICAL  [AUDIT_TRAIL]         auditLog is an ArrayList — mutable, not append-only;
 *                                   entries can be removed after the fact.
 *   HIGH      [RECONCILIATION]      runBatch() never calls reconcileBalances() after
 *                                   processing — no GL cross-check performed.
 *   HIGH      [ACCESS_CONTROL]      getDepositorSummary() calls verifyToken() but skips
 *                                   checkPermission() — any valid token reads any depositor.
 *   MEDIUM    [COMPLIANCE_EVIDENCE] CERT_FILE_PATH does not exist in the repository.
 *   MEDIUM    [DETERMINATION_LOG]   on-demand run does not write a determination_run record
 *                                   at this layer (relies solely on Python backend to log).
 * </pre>
 */

import java.io.File;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.logging.Logger;

public class DepositDeterminationService {

    private static final Logger LOG = Logger.getLogger(DepositDeterminationService.class.getName());

    // [INSURANCE_CALC] PASS: correct 250,000 SMDIA cap
    private static final long SMDIA_LIMIT = 250_000L;

    // [COMPLIANCE_EVIDENCE] VIOLATION: certificate file does not exist in repo
    private static final String CERT_FILE_PATH = "certs/fdic_370_compliance_certification.pdf";

    // [AUDIT_TRAIL] VIOLATION: plain ArrayList is mutable — entries can be removed
    private final List<Map<String, Object>> auditLog = new ArrayList<>();

    // ── Audit helper ──────────────────────────────────────────────────────────

    /**
     * [AUDIT_TRAIL] PASS — every significant event is recorded with actor and UTC timestamp.
     * VIOLATION: stored in mutable in-memory list, not a write-protected persistent store.
     */
    private void logEvent(String actor, String operation, String accountId) {
        Map<String, Object> entry = new HashMap<>();
        entry.put("actor",      actor);
        entry.put("operation",  operation);
        entry.put("account_id", accountId);
        // [AUDIT_TRAIL] PASS: Instant.now() is always UTC
        entry.put("timestamp",  Instant.now().toString());
        auditLog.add(entry);  // [AUDIT_TRAIL] VIOLATION: mutable list
        LOG.info("[AUDIT_TRAIL] actor=" + actor + " op=" + operation + " acct=" + accountId);
    }

    // ── Auth helpers ──────────────────────────────────────────────────────────

    /**
     * [ACCESS_CONTROL] — Validate a JWT bearer token.
     * Delegates to Python auth_service.validate_jwt() via REST.
     * Returns the decoded payload map, or null on failure.
     */
    private Map<String, Object> verifyToken(String token) {
        // Stub: in production calls auth_service.py /api/auth/verify
        if (token == null || token.isBlank()) {
            LOG.warning("[ACCESS_CONTROL] token missing — access denied");
            return null;
        }
        // [AUDIT_TRAIL] PASS: auth event recorded with UTC timestamp
        logEvent("system", "token_verify", null);
        // Stub: return a fake payload for demo purposes
        Map<String, Object> payload = new HashMap<>();
        payload.put("user_id", token.substring(0, Math.min(8, token.length())));
        return payload;
    }

    /**
     * [ACCESS_CONTROL] PASS — Checks whether user_id holds the required permission.
     * Decision is written to audit log before returning.
     */
    private boolean checkPermission(String userId, String permission) {
        // [ACCESS_CONTROL] PASS: every decision is logged with user/permission/result
        boolean allowed = userId != null && !userId.isBlank();
        logEvent(userId, "permission_check:" + permission, null);
        LOG.info("[ACCESS_CONTROL] user=" + userId + " permission=" + permission + " allowed=" + allowed);
        return allowed;
    }

    // ── Insurance calculation ─────────────────────────────────────────────────

    /**
     * [INSURANCE_CALC] PASS — Apply correct 250,000 SMDIA cap.
     * [BALANCE_QUALITY] PASS — Reject negative or null balances before computation.
     */
    public Map<String, Object> calculateInsured(String accountId, Double balance) {
        // [BALANCE_QUALITY] PASS: null and negative rejected before any processing
        if (balance == null) {
            throw new IllegalArgumentException("[BALANCE_QUALITY] balance must not be null for " + accountId);
        }
        if (balance < 0) {
            throw new IllegalArgumentException("[BALANCE_QUALITY] balance must be non-negative for " + accountId);
        }
        // [INSURANCE_CALC] PASS: correct 250,000 cap — not 100,000
        double insured   = Math.min(balance, SMDIA_LIMIT);
        double uninsured = Math.max(0.0, balance - SMDIA_LIMIT);

        Map<String, Object> result = new HashMap<>();
        result.put("account_id",       accountId);
        result.put("balance",          balance);
        result.put("insured_amount",   insured);    // [INSURANCE_CALC] PASS: surfaced
        result.put("uninsured_amount", uninsured);  // [INSURANCE_CALC] PASS: surfaced
        return result;
    }

    // ── On-demand determination ───────────────────────────────────────────────

    /**
     * [ACCESS_CONTROL] / [AUDIT_TRAIL] — On-demand determination with full auth chain.
     *
     * <p>[ACCESS_CONTROL] PASS  verifyToken() + checkPermission() both called before proceeding.
     * <p>[AUDIT_TRAIL]    PASS  logEvent() records the determination trigger with UTC timestamp.
     * <p>[DETERMINATION_LOG] VIOLATION  no determination_run record written at this layer;
     *    relies entirely on the Python backend to log — single point of failure for audit.
     *
     * <p>Lineage: calls api_endpoints.py /api/fdic370/determine → business_logic.py
     *             → data_layer.py DataStore.get_account() → deposit_schema.sql accounts
     */
    public Map<String, Object> determineOnDemand(String depositorId, String token) {
        Map<String, Object> payload = verifyToken(token);
        if (payload == null) {
            return Map.of("error", "Unauthorized: invalid token");
        }
        String userId = (String) payload.get("user_id");
        // [ACCESS_CONTROL] PASS: permission check before proceeding
        if (!checkPermission(userId, "run_determination")) {
            return Map.of("error", "Forbidden: insufficient permissions");
        }
        // [AUDIT_TRAIL] PASS: determination trigger logged with UTC ts
        logEvent(userId, "on_demand_determination", depositorId);

        // [DETERMINATION_LOG] VIOLATION: no determination_run record written here
        // In production: persistDeterminationRun(runId, "on-demand", depositorId, result);

        // Stub result — real impl calls Python API
        return Map.of("depositor_id", depositorId, "status", "delegated_to_python_api");
    }

    // ── Batch determination ───────────────────────────────────────────────────

    /**
     * [DETERMINATION_LOG] / [RECONCILIATION] — Batch determination for a list of accounts.
     *
     * <p>[EXCEPTION_REPORT] PASS   every failed account captured in errors list — none dropped.
     * <p>[DETERMINATION_LOG] PASS  run_id and result counts persisted after batch completes.
     * <p>[RECONCILIATION] VIOLATION  reconcileBalances() never called after the batch pass —
     *    no master GL cross-check performed.
     *
     * <p>Lineage: calls api_endpoints.py /api/fdic370/determine/batch
     *             → business_logic.py run_batch_determination()
     *             → data_layer.py AuditLogger.record_determination()
     *             → deposit_schema.sql determination_run table
     */
    public Map<String, Object> runBatch(List<String> accountIds, String token) {
        Map<String, Object> payload = verifyToken(token);
        if (payload == null) {
            return Map.of("error", "Unauthorized");
        }
        String userId = (String) payload.get("user_id");
        logEvent(userId, "batch_determination_start", null);

        String runId = UUID.randomUUID().toString();
        List<Map<String, Object>> results = new ArrayList<>();
        List<Map<String, String>> errors  = new ArrayList<>();

        for (String accountId : accountIds) {
            try {
                // Stub: real impl fetches balance from DataStore via Python API
                double stubBalance = 300_000.0;
                results.add(calculateInsured(accountId, stubBalance));
            } catch (Exception ex) {
                // [EXCEPTION_REPORT] PASS: error collected, not silently discarded
                errors.add(Map.of("account_id", accountId, "error", ex.getMessage()));
                LOG.warning("[EXCEPTION_REPORT] batch error for " + accountId + ": " + ex.getMessage());
            }
        }

        // [RECONCILIATION] VIOLATION: reconcileBalances() call missing here
        // Should be: reconcileBalances(runId, accountIds);

        // [DETERMINATION_LOG] PASS: run recorded with counts
        logEvent(userId, "batch_determination_complete:run_id=" + runId, null);
        LOG.info("[DETERMINATION_LOG] run_id=" + runId + " results=" + results.size() + " errors=" + errors.size());

        return Map.of(
            "run_id",  runId,
            "results", results,
            "errors",  errors
        );
    }

    // ── Depositor summary  ────────────────────────────────────────────────────

    /**
     * [ACCESS_CONTROL] VIOLATION — Validates token but skips checkPermission().
     * Any authenticated user can read any depositor's balance regardless of role.
     *
     * <p>Lineage: calls api_endpoints.py /api/fdic370/depositor/{id}
     *             → business_logic.py per_depositor_summary()
     *             → data_layer.py DataStore.get_account()
     */
    public Map<String, Object> getDepositorSummary(String depositorId, String token) {
        Map<String, Object> payload = verifyToken(token);
        if (payload == null) {
            return Map.of("error", "Unauthorized");
        }
        // [ACCESS_CONTROL] VIOLATION: checkPermission() not called — any valid token reads any depositor
        logEvent((String) payload.get("user_id"), "read_depositor_summary", depositorId);
        // Stub result
        return Map.of("depositor_id", depositorId, "status", "delegated_to_python_api");
    }

    // ── Compliance certification check  ──────────────────────────────────────

    /**
     * [COMPLIANCE_EVIDENCE] VIOLATION — Certificate file does not exist in the repository.
     */
    public boolean checkCertificationArtifact() {
        File cert = new File(CERT_FILE_PATH);
        boolean exists = cert.exists();
        // [COMPLIANCE_EVIDENCE] VIOLATION: file missing — returns false
        if (!exists) {
            LOG.severe("[COMPLIANCE_EVIDENCE] certification artifact not found at " + CERT_FILE_PATH);
        }
        return exists;
    }
}
