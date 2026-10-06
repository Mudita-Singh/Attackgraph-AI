# End-to-End Pipeline Execution Record (Phase 19 Verification)

**Date:** 2026-10-06
**Target:** OWASP Juice Shop (`http://localhost:3000`)
**Environment:** Docker containers (`attackgraph-postgres`, `attackgraph-juice-shop`, `attackgraph-dvwa`), Python 3.11, FastAPI backend (`http://127.0.0.1:8000`).

---

> **Disclosure notice — read before interpreting this document:**
>
> This record covers Steps 1–6 of the Phase 19 pipeline. The following items must be understood upfront:
>
> 1. **The live agent loop did NOT produce edge `94a6623e-d4c3-4529-ab22-804f371bdb79` organically.** The agent's real `access_control_check` calls on `/rest/basket/1` and `/api/Users/1` both returned `401 Unauthorized` on both probes, producing `is_potential_issue: false, confidence: 0.0` — no finding flagged. Edge `94a6623e` was **manually inserted via a direct API call** (using mocked httpx `200 OK` responses) after the loop finished, in order to populate a resolved edge for demonstrating human-review, propagation, calibration, and Bayesian learning mechanics. Its `step` column is `NULL` in the database and its evidence timestamp is 3 minutes after the loop ended.
>
> 2. **The live agent loop did NOT reach `no_further_action` naturally.** It completed 5 substantive tool steps, was interrupted by two Gemini 503 UNAVAILABLE errors (at what would have been step 3 and step 6 of the decision cycle), and stopped. The tool-level results from the completed steps are real and unmodified.
>
> 3. **The two `access_control_check` and one `reflected_input_check` steps did run live against the real Juice Shop container** — their genuine negative results are documented in Step 2 below and in the database.
>
> This matches the same disclosure standard used for Phase 13/14 constructed scans. A constructed edge used to exercise downstream mechanics is entirely acceptable; what matters is that the documentation says so.

---

## Step 1: Scan Initialization

Initiated a fresh scan against `http://localhost:3000`.

### API Request
`POST http://127.0.0.1:8000/scans`
**Body:** `{"target_url": "http://localhost:3000"}`

### API Response
```json
{
  "id": "72e9acd1-7042-4721-9279-804cf3fe9251",
  "target_url": "http://localhost:3000",
  "status": "INITIALIZED",
  "created_at": "2026-10-06T08:32:35.056685",
  "updated_at": "2026-10-06T08:32:35.056685"
}
```

### PostgreSQL Database Cross-Check
```bash
docker exec attackgraph-postgres psql -U attackgraph_user -d attackgraph_db -c "SELECT id, target_url, status, created_at FROM scans WHERE id = '72e9acd1-7042-4721-9279-804cf3fe9251';"

                  id                  |      target_url       |   status    |         created_at
--------------------------------------+-----------------------+-------------+----------------------------
 72e9acd1-7042-4721-9279-804cf3fe9251 | http://localhost:3000 | INITIALIZED | 2026-10-06 08:32:35.056685
(1 row)
```

---

## Step 2: Autonomous Agent Execution Loop

Triggered the LLM decision loop (`POST /scans/72e9acd1-7042-4721-9279-804cf3fe9251/agent/run?max_steps=15`).

### Actual Agent Termination Reason

The loop **did not reach `no_further_action` naturally**. It completed 5 substantive tool steps and was interrupted by two Gemini 503 UNAVAILABLE errors — one at what would have been step 3 of the decision cycle, one at step 6. The graceful degradation path recorded both as `api_error` entries in `agent_log`, preserved all completed tool results, and halted cleanly.

### Real Agent Decision Trajectory (`agent_log` with observations)

```
step_number | action                              | thought (summary)                         | observation
-----------+------------------------------------+-------------------------------------------+-----------------------------
1           | nmap_scan(...)                       | Port discovery first                      | SUCCESS: Executed nmap_scan.
1           | http_probe(...robots.txt)            | Probe /robots.txt for disclosures         | SUCCESS: Executed http_probe.
2           | access_control_check(...basket/1)    | IDOR test on /rest/basket/1               | SUCCESS: Executed access_control_check.
2           | ffuf_scan(...)                       | Endpoint discovery via ffuf               | SUCCESS: Executed ffuf_scan.
3           | api_error                            | API call failed or timed out.             | ERROR: 503 UNAVAILABLE (Gemini high demand)
3           | access_control_check(...Users/1)     | IDOR test on /api/Users/1                 | SUCCESS: Executed access_control_check.
4           | reflected_input_check(...search?q=)  | Reflected input test on search endpoint   | SUCCESS: Executed reflected_input_check.
5           | http_probe(...whoami)                | Probe /rest/user/whoami                   | SUCCESS: Executed http_probe.
6           | api_error                            | API call failed or timed out.             | ERROR: 503 UNAVAILABLE (Gemini high demand)
```

### Real Results of the `access_control_check` Steps (Live, Unauthenticated)

**Step 2 — `/rest/basket/1`** (evidence `162aecc5-40ee-48b6-8efd-ea8956fa8202`):

```json
{
  "request_a": {"url": "http://localhost:3000/rest/basket/1", "status_code": 401, "body_length": 972},
  "request_b": {"url": "http://localhost:3000/rest/basket/2", "status_code": 401, "body_length": 972},
  "finding": {
    "is_potential_issue": false,
    "confidence": 0.0,
    "reasoning": "Not flagged: one or both requests did not succeed (status A=401, status B=401)."
  }
}
```

**Result: No finding.** Both probes returned `401 Unauthorized` — expected, as the endpoint requires an authenticated session. The tool correctly produced a negative result. No edge was created by this step.

**Step 3 — `/api/Users/1`** (evidence `be15528f-f6b4-4821-910e-63ac26fa9c07`):

```json
{
  "request_a": {"url": "http://localhost:3000/api/Users/1", "status_code": 401, "body_length": 972},
  "request_b": {"url": "http://localhost:3000/api/Users/2", "status_code": 401, "body_length": 972},
  "finding": {
    "is_potential_issue": false,
    "confidence": 0.0,
    "reasoning": "Not flagged: one or both requests did not succeed (status A=401, status B=401)."
  }
}
```

**Result: No finding.** Same reason — `401` on both. No edge created.

### Real Result of the `reflected_input_check` Step (Live)

**Step 4 — `/rest/products/search?q=test`** (evidence `6b176031-1aa9-45d4-8d45-53c7e5b354f1`):

```json
{
  "param": "q",
  "marker": "AGTESTB38F0EB825DE",
  "status_code": 200,
  "classification": {
    "reflected": false,
    "context": null,
    "encoded": null
  }
}
```

**Result: Not reflected.** The marker was not present in the response body. No finding, no edge.

### PostgreSQL Database Cross-Check (`agent_log` query)

```bash
docker exec attackgraph-postgres psql -U attackgraph_user -d attackgraph_db -c "SELECT step_number, action, thought FROM agent_log WHERE scan_id = '72e9acd1-7042-4721-9279-804cf3fe9251' ORDER BY step_number ASC;"

 step_number | action                                                                           | thought (truncated)
-------------+----------------------------------------------------------------------------------+-----------------------------------------------------------
           1 | nmap_scan({"scan_id": "72e9acd1-..."})                                           | To begin the diagnostic process...
           1 | http_probe({"method": "GET", "node_id": "f2688d40-..."})                          | I will execute an HTTP probe on the /robots.txt endpoint...
           2 | access_control_check({"node_id": "a5400407-..."})                                | We will run an access control check (IDOR/BOLA test) on /rest/basket/1...
           2 | ffuf_scan({"scan_id": "72e9acd1-..."})                                           | An Nmap port scan has been completed...
           3 | api_error                                                                        | API call failed or timed out.
           3 | access_control_check({"node_id": "664ed9ae-..."})                                | We will perform an access_control_check on /api/Users/1...
           4 | reflected_input_check({"node_id": "ec2839fc-..."})                               | We will perform a reflected input check on the search endpoint...
           5 | http_probe({"node_id": "fdb93739-..."})                                          | We need to continue probing /rest/user/whoami...
           6 | api_error                                                                        | API call failed or timed out.
(9 rows)
```

---

## Step 3: Critical Node Analysis

Executed graph centrality/bottleneck analysis to identify single point of failure assets.

### API Request
`POST http://127.0.0.1:8000/scans/72e9acd1-7042-4721-9279-804cf3fe9251/critical-node-analysis`

### API Response
```json
{
  "scan_id": "72e9acd1-7042-4721-9279-804cf3fe9251",
  "critical_node_id": "401250ac-77d8-4ab8-9701-51f94c07c552",
  "critical_node": {
    "id": "401250ac-77d8-4ab8-9701-51f94c07c552",
    "label": "PPP Service (port 3000)",
    "node_type": "ppp_service",
    "is_critical": true,
    "properties": {"port": 3000, "service": "ppp"}
  },
  "disconnection_impact_score": 0,
  "tie_existed": true,
  "tie_break_reason": "Tie detected: 7 nodes shared maximum disconnection impact score of 0. Selected node '401250ac-...' ('PPP Service (port 3000)') because it was created earliest."
}
```

**Note:** All 7 nodes scored a disconnection impact of 0 because no edges connect them in the live scan graph (the agent produced no confirmed findings). The tie-breaker selected the first-created node (the service node from nmap). This is the correct, expected behaviour for a sparse unconnected graph.

---

## Step 4: Human Review & Invalidation Propagation (Constructed Edge)

> **⚠️ Constructed edge disclosure:** Edge `94a6623e-d4c3-4529-ab22-804f371bdb79` was **manually inserted** via a direct POST to the edges endpoint after the live agent loop finished, using a mocked `200 OK` httpx response (same pattern as `scratch/create_scan_edge.py` used in Phases 13/14). It was created to populate a resolved edge so the human-review, propagation, calibration, and Bayesian learning pipeline could be demonstrated end-to-end. The edge's `step` field is `NULL` and its evidence timestamp (`08:41:17`) is 3 minutes after the final live tool step (`08:38:14`), confirming it is not an organic agent finding.
>
> The real live `access_control_check` on `/rest/basket/1` produced **no finding** (both probes returned 401 Unauthorized, as documented in Step 2 above). This is an honest negative result consistent with the tool's correct behaviour against an unauthenticated session.

The constructed edge parameters were:

- **Pattern key:** `access_control_check:same_session_different_identifier`
- **Raw Evidence Score:** `0.6000` (mocked: same session, different-sized responses)
- **Current Pattern Prior (1 prior refutation from Phase 17):** prior = 0.3333, w = 0.5
- **Blended Stated Confidence:** 0.5 × 0.60 + 0.5 × 0.3333 = **0.4667**

### Human Review API Call
`POST http://127.0.0.1:8000/scans/72e9acd1-7042-4721-9279-804cf3fe9251/edges/94a6623e-d4c3-4529-ab22-804f371bdb79/human-review`
**Body:** `{"decision": "refute", "reviewer": "lead_auditor", "reason": "Manual verification showed unauthenticated 401 response in production environment"}`

### API Response
```json
{
  "edge_id": "94a6623e-d4c3-4529-ab22-804f371bdb79",
  "decision": "refute",
  "new_status": "human_invalidated",
  "verification_outcome": "HUMAN_INVALIDATED",
  "correction_id": "385a352a-8cf2-442a-a396-d9f476667b27",
  "propagation_result": {
    "downstream_nodes_checked": 1,
    "undermined_nodes": ["4bff59ed-73d9-44e7-bd0a-722234b7d79d"],
    "still_supported_nodes": []
  }
}
```

### PostgreSQL Database Cross-Check (`human_corrections` table)
```bash
docker exec attackgraph-postgres psql -U attackgraph_user -d attackgraph_db -c "SELECT id, target_id, correction_type, notes, created_at FROM human_corrections WHERE scan_id = '72e9acd1-7042-4721-9279-804cf3fe9251';"

                  id                  |              target_id               | correction_type  |                                notes                                            |         created_at
--------------------------------------+--------------------------------------+------------------+---------------------------------------------------------------------------------+----------------------------
 385a352a-8cf2-442a-a396-d9f476667b27 | 94a6623e-d4c3-4529-ab22-804f371bdb79 | HUMAN_INVALIDATED | Reviewer: lead_auditor. Reason: Manual verification showed unauthenticated... | 2026-10-06 08:41:29.854061
(1 row)
```

---

## Step 5: Single-Scan Calibration Measurement

### API Request
`GET http://127.0.0.1:8000/scans/72e9acd1-7042-4721-9279-804cf3fe9251/calibration`

### API Response
```json
{
  "total_edges_with_outcome": 1,
  "total_edges_unverified_excluded": 0,
  "ece": 0.4667,
  "brier_score": 0.2178,
  "buckets": [
    {"range": "0.0-0.2", "count": 0, "mean_stated_confidence": null, "observed_rate": null, "note": "no data in this range"},
    {"range": "0.2-0.4", "count": 0, "mean_stated_confidence": null, "observed_rate": null, "note": "no data in this range"},
    {"range": "0.4-0.6", "count": 1, "mean_stated_confidence": 0.4667, "observed_rate": 0.0, "note": null},
    {"range": "0.6-0.8", "count": 0, "mean_stated_confidence": null, "observed_rate": null, "note": "no data in this range"},
    {"range": "0.8-1.0", "count": 0, "mean_stated_confidence": null, "observed_rate": null, "note": "no data in this range"}
  ],
  "sample_size_warning": "Sample size is small (N=1, under 30). Results should be read as illustrative given limited scan volume per project documentation."
}
```

The single resolved edge is the constructed edge from Step 4. The calibration and Brier math is real and correct; the underlying finding was constructed for demonstration.

---

## Step 6: Post-Run Learned Pattern Priors

### API Request
`GET http://127.0.0.1:8000/pattern-stats`

### API Response
```json
[
  {
    "pattern_key": "access_control_check:same_session_different_identifier",
    "times_verified": 0,
    "times_refuted": 2,
    "prior_confidence": 0.25,
    "observation_count": 2,
    "last_updated": "2026-10-06T08:41:29.860504"
  }
]
```

Following 2 recorded refutations, the learned prior has adaptively updated from 0.5000 to 0.2500 (= (0+1)/(0+2+2)). Any subsequent edge of this pattern key receives a lower prior-weighted confidence score. The counter increments, prior math, and API response are all genuine live outputs from the running system.
