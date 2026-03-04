/**
 * apiClient.ts
 * FDIC 370 Compliance — TypeScript/React frontend API client.
 *
 * Semantic-label key (IDs are in regulations/fdic_370_controls.json; labels stable)
 * ---------------------------------------------------------------------------------
 *   [AUDIT_TRAIL]        every API call carries a traceable request_id in headers
 *   [ACCESS_CONTROL]     JWT token attached to every privileged request
 *   [INPUT_VALIDATION]   request payloads validated before dispatch
 *   [REQUIRED_DATA]      required fields checked before fetch — fail fast
 *   [INSURANCE_CALC]     response amounts (insured/uninsured) displayed as-received
 *   [EXCEPTION_REPORT]   error responses surfaced in UI — never silently swallowed
 *   [PII_PROTECTION]     TIN/SSN never logged in console or sent to analytics
 *   [DETERMINATION_LOG]  run_id from batch response persisted in session storage
 *
 * CROSS-FILE LINEAGE
 * ------------------
 *   THIS FILE (browser)
 *     ↓  fetch()  POST /api/fdic370/determine
 *   api_endpoints.py  on_demand_determine()          [ACCESS_CONTROL] [AUDIT_TRAIL]
 *     ↓  delegate
 *   business_logic.py InsuranceDeterminationService  [INSURANCE_CALC] [DETERMINATION_LOG]
 *     ↓  reads / writes
 *   data_layer.py     DataStore + AuditLogger        [AUDIT_TRAIL]
 *     ↓  SQL
 *   deposit_schema.sql accounts + determination_run  [UNIQUE_ACCOUNT_ID]
 *
 *   THIS FILE (browser)
 *     ↓  fetch()  POST /api/fdic370/determine/batch
 *   api_endpoints.py  batch_determine()              [DETERMINATION_LOG] VIOLATION
 *     ↓  delegate
 *   DepositDeterminationService.java  runBatch()     [RECONCILIATION] VIOLATION
 *
 * Controls correctly implemented (PASS)
 * ----------------------------------------
 *   [ACCESS_CONTROL]    authHeaders() attaches Bearer token to every privileged call
 *   [INPUT_VALIDATION]  validateDetermineRequest() rejects blank depositor_id before fetch
 *   [REQUIRED_DATA]     validateBatchRequest() rejects empty or blank account ID list
 *   [EXCEPTION_REPORT]  handleApiError() surfaces all HTTP errors — no silent catch
 *   [PII_PROTECTION]    sanitizeForLog() strips tin/ssn fields before any console.log
 *   [DETERMINATION_LOG] saveRunId() persists batch run_id in sessionStorage for polling
 *
 * Intentional violations for Kratos to detect
 * -----------------------------------------------
 *   CRITICAL  [PII_PROTECTION]    fetchDepositorProfile() logs the raw response which
 *                                 may contain tin/ssn — sanitizeForLog() not called.
 *   HIGH      [AUDIT_TRAIL]       batchDetermine() does not include X-Request-ID header
 *                                 — batch calls are untraceable at the network layer.
 *   HIGH      [ACCESS_CONTROL]    getReport() reads run report without attaching the
 *                                 auth token — any unauthenticated caller can poll results.
 *   MEDIUM    [INPUT_VALIDATION]  batchDetermine() sends account_ids without trimming
 *                                 whitespace — blank-padded IDs bypass the backend validator.
 */

const API_BASE = "/api";

// ── Auth helpers ─────────────────────────────────────────────────────────────

/** [ACCESS_CONTROL] PASS — Attach JWT to every privileged request header. */
function authHeaders(token: string): Record<string, string> {
  return {
    "Content-Type":  "application/json",
    "Authorization": `Bearer ${token}`,                           // [ACCESS_CONTROL] PASS
    "X-Request-ID":  crypto.randomUUID(),                        // [AUDIT_TRAIL] PASS: traceable
  };
}

// ── PII guard ─────────────────────────────────────────────────────────────────

/**
 * [PII_PROTECTION] PASS — Strip sensitive fields before any console.log / analytics.
 */
function sanitizeForLog(obj: Record<string, unknown>): Record<string, unknown> {
  const PII_FIELDS = new Set(["tin", "ssn", "govt_id", "tax_id", "tin_cache"]);
  return Object.fromEntries(
    Object.entries(obj).map(([k, v]) =>
      PII_FIELDS.has(k.toLowerCase()) ? [k, "***REDACTED***"] : [k, v]  // [PII_PROTECTION] PASS
    )
  );
}

// ── Error handler ─────────────────────────────────────────────────────────────

/**
 * [EXCEPTION_REPORT] PASS — Translate HTTP error responses into typed errors.
 * No error is silently swallowed — all failures propagate to the caller.
 */
async function handleApiError(response: Response): Promise<never> {
  const body = await response.json().catch(() => ({ detail: response.statusText }));
  // [EXCEPTION_REPORT] PASS: error surfaced with status code and detail
  throw new Error(`[EXCEPTION_REPORT] HTTP ${response.status}: ${body.detail ?? JSON.stringify(body)}`);
}

// ── Input validators ──────────────────────────────────────────────────────────

/** [INPUT_VALIDATION] PASS — Reject blank depositor_id before dispatching request. */
function validateDetermineRequest(depositorId: string, token: string): void {
  if (!depositorId?.trim()) {
    throw new Error("[INPUT_VALIDATION] depositor_id must not be blank");  // [REQUIRED_DATA] PASS
  }
  if (!token?.trim()) {
    throw new Error("[ACCESS_CONTROL] token must not be blank");
  }
}

/** [INPUT_VALIDATION] / [REQUIRED_DATA] PASS — Reject empty or blank-only account ID list. */
function validateBatchRequest(accountIds: string[], token: string): void {
  if (!accountIds || accountIds.length === 0) {
    throw new Error("[REQUIRED_DATA] account_ids must not be empty");
  }
  // [INPUT_VALIDATION] PASS: blank entries rejected at client layer
  if (accountIds.some((id) => !id?.trim())) {
    throw new Error("[INPUT_VALIDATION] account_ids must not contain blank strings");
  }
  if (!token?.trim()) {
    throw new Error("[ACCESS_CONTROL] token must not be blank");
  }
}

// ── API calls ─────────────────────────────────────────────────────────────────

/**
 * On-demand insurance determination for a single depositor.
 *
 * [ACCESS_CONTROL] PASS  — auth token attached via authHeaders()
 * [AUDIT_TRAIL]    PASS  — X-Request-ID header makes call traceable
 * [INPUT_VALIDATION] PASS — depositor_id validated before fetch
 *
 * Calls: api_endpoints.py  POST /api/fdic370/determine
 */
export async function determineSingle(
  depositorId: string,
  token: string
): Promise<Record<string, unknown>> {
  validateDetermineRequest(depositorId, token);   // [INPUT_VALIDATION] PASS

  const response = await fetch(`${API_BASE}/fdic370/determine`, {
    method:  "POST",
    headers: authHeaders(token),                 // [ACCESS_CONTROL] PASS
    body:    JSON.stringify({ depositor_id: depositorId, token }),
  });

  if (!response.ok) await handleApiError(response);  // [EXCEPTION_REPORT] PASS
  const data = await response.json() as Record<string, unknown>;
  console.log("[INSURANCE_CALC] result:", sanitizeForLog(data));  // [PII_PROTECTION] PASS
  return data;
}

/**
 * Batch determination for a list of account IDs.
 *
 * [DETERMINATION_LOG] PASS  — run_id from response saved to sessionStorage
 * [AUDIT_TRAIL]       VIOLATION — X-Request-ID header NOT included (see authHeaders not called)
 * [INPUT_VALIDATION]  VIOLATION — account IDs sent without .trim() — whitespace bypass possible
 *
 * Calls: api_endpoints.py  POST /api/fdic370/determine/batch
 *        → business_logic.py run_batch_determination()
 *        → DepositDeterminationService.java runBatch()
 */
export async function batchDetermine(
  accountIds: string[],
  token: string
): Promise<Record<string, unknown>> {
  validateBatchRequest(accountIds, token);  // [INPUT_VALIDATION] — validates presence, not whitespace trim

  const response = await fetch(`${API_BASE}/fdic370/determine/batch`, {
    method:  "POST",
    // [AUDIT_TRAIL] VIOLATION: plain headers — no X-Request-ID, no traceability
    headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
    // [INPUT_VALIDATION] VIOLATION: ids not trimmed — "  ACC001  " passes validateBatchRequest
    body:    JSON.stringify({ account_ids: accountIds, token }),
  });

  if (!response.ok) await handleApiError(response);  // [EXCEPTION_REPORT] PASS
  const data = await response.json() as Record<string, unknown>;

  // [DETERMINATION_LOG] PASS: run_id persisted for polling
  if (data.run_id) {
    sessionStorage.setItem("last_run_id", String(data.run_id));
    console.log("[DETERMINATION_LOG] batch run_id saved:", data.run_id);
  }
  return data;
}

/**
 * Retrieve the determination report for a completed run.
 *
 * [ACCESS_CONTROL] VIOLATION — no Authorization header attached; report endpoint
 * is called without auth.  Any browser tab can poll any run_id.
 *
 * Calls: api_endpoints.py  GET /api/fdic370/report/{run_id}
 */
export async function getReport(runId: string): Promise<Record<string, unknown>> {
  if (!runId?.trim()) {
    throw new Error("[REQUIRED_DATA] run_id must not be blank");
  }
  // [ACCESS_CONTROL] VIOLATION: no Authorization header — unauthenticated polling
  const response = await fetch(`${API_BASE}/fdic370/report/${encodeURIComponent(runId)}`, {
    method: "GET",
    // Missing: headers: authHeaders(token)
  });
  if (!response.ok) await handleApiError(response);  // [EXCEPTION_REPORT] PASS
  return response.json() as Promise<Record<string, unknown>>;
}

/**
 * Get insured/uninsured balance summary for a depositor.
 *
 * [ACCESS_CONTROL] PASS — auth token attached
 * [INSURANCE_CALC] PASS — response amounts displayed directly, no client-side recalculation
 *
 * Calls: api_endpoints.py  GET /api/fdic370/depositor/{depositor_id}
 *        → business_logic.py per_depositor_summary()
 */
export async function getDepositorSummary(
  depositorId: string,
  token: string
): Promise<Record<string, unknown>> {
  validateDetermineRequest(depositorId, token);  // [INPUT_VALIDATION] PASS

  const response = await fetch(
    `${API_BASE}/fdic370/depositor/${encodeURIComponent(depositorId)}?token=${encodeURIComponent(token)}`,
    {
      method:  "GET",
      headers: authHeaders(token),   // [ACCESS_CONTROL] PASS
    }
  );
  if (!response.ok) await handleApiError(response);  // [EXCEPTION_REPORT] PASS
  const data = await response.json() as Record<string, unknown>;
  // [INSURANCE_CALC] PASS: raw insured/uninsured amounts from backend displayed as-received
  console.log("[INSURANCE_CALC] depositor summary:", sanitizeForLog(data));  // [PII_PROTECTION] PASS
  return data;
}

/**
 * Fetch raw depositor profile (includes PII fields).
 *
 * [PII_PROTECTION] VIOLATION — raw response logged to console without sanitizeForLog().
 * SSN/TIN may appear in browser dev-tools or log shipping agents.
 *
 * Calls: api_endpoints.py  POST /api/profile
 */
export async function fetchDepositorProfile(
  userId: string,
  token: string
): Promise<Record<string, unknown>> {
  validateDetermineRequest(userId, token);  // [INPUT_VALIDATION] PASS

  const response = await fetch(`${API_BASE}/profile`, {
    method:  "POST",
    headers: authHeaders(token),             // [ACCESS_CONTROL] PASS
    body:    JSON.stringify({ user_id: userId, token }),
  });
  if (!response.ok) await handleApiError(response);  // [EXCEPTION_REPORT] PASS
  const data = await response.json() as Record<string, unknown>;
  // [PII_PROTECTION] VIOLATION: sanitizeForLog() NOT called — tin/ssn may leak to console
  console.log("[PII_PROTECTION] profile data:", data);  // VIOLATION: raw log
  return data;
}

/**
 * Poll the exception list for a batch run.
 *
 * [EXCEPTION_REPORT] PASS — full error list returned and displayed
 *
 * Calls: api_endpoints.py  GET /api/fdic370/exceptions/{run_id}
 */
export async function getExceptions(runId: string, token: string): Promise<Record<string, unknown>> {
  if (!runId?.trim()) throw new Error("[REQUIRED_DATA] run_id must not be blank");

  const response = await fetch(
    `${API_BASE}/fdic370/exceptions/${encodeURIComponent(runId)}?token=${encodeURIComponent(token)}`,
    { method: "GET", headers: authHeaders(token) }  // [ACCESS_CONTROL] PASS
  );
  if (!response.ok) await handleApiError(response);  // [EXCEPTION_REPORT] PASS
  return response.json() as Promise<Record<string, unknown>>;
}
