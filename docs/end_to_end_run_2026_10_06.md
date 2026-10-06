# End-to-End Pipeline Execution Record (Phase 19 Verification)

**Date:** 2026-10-06  
**Target:** OWASP Juice Shop (`http://localhost:3000`)  
**Environment:** Docker containers (`attackgraph-postgres`, `attackgraph-juice-shop`, `attackgraph-dvwa`), Python 3.11, FastAPI backend (`http://127.0.0.1:8000`).

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

### Agent Decision Trajectory (`agent_log`)
The agent executed sequential tool actions:
1. `nmap_scan`: Discovered port 3000 service node `PPP Service (port 3000)`.
2. `ffuf_scan`: Discovered 6 web application endpoints (`/robots.txt`, `/assets`, `/rest/basket/1`, `/api/Users/1`, `/rest/user/whoami`, `/rest/products/search?q=test`).
3. `http_probe`: Probed `/robots.txt`.
4. `access_control_check`: Tested path-based access control on `/rest/basket/1`.
5. `access_control_check`: Tested path-based access control on `/api/Users/1`.
6. `reflected_input_check`: Tested reflection context on `/rest/products/search?q=test`.
7. `http_probe`: Probed `/rest/user/whoami`.

### PostgreSQL Database Cross-Check (`agent_log` query)
```bash
docker exec attackgraph-postgres psql -U attackgraph_user -d attackgraph_db -c "SELECT step_number, action, thought FROM agent_log WHERE scan_id = '72e9acd1-7042-4721-9279-804cf3fe9251' ORDER BY step_number ASC;"

 step_number |                                      action                                      |                                                                                                                        thought                                                                                                                         
-------------+----------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
           1 | nmap_scan({"scan_id": "72e9acd1-7042-4721-9279-804cf3fe9251"})                   | To begin the diagnostic process on the target environment, the initial step is port and service discovery to identify available services. I will execute an Nmap port scan against the target.
           1 | http_probe({"method": "GET", "node_id": "f2688d40-134b-4c09-b20e-aa2464c0098d"}) | I will execute an HTTP probe on the `/robots.txt` endpoint (`node_id: f2688d40-134b-4c09-b20e-aa2464c0098d`) to inspect the response body and check for disclosed paths or sensitive data.
           2 | access_control_check({"node_id": "a5400407-2b1a-448e-9d1b-e8493315b598"})        | We will run an access control check (IDOR/BOLA test) on the endpoint `/rest/basket/1` (`a5400407-2b1a-448e-9d1b-e8493315b598`) to test whether modifying the basket identifier in the path allows accessing authorization-restricted user basket data.
           2 | ffuf_scan({"scan_id": "72e9acd1-7042-4721-9279-804cf3fe9251"})                   | An Nmap port scan has been completed on the target. The next step in web application security assessment is endpoint and directory discovery via `ffuf_scan` to locate accessible web application routes and interfaces for further inspection.
           3 | access_control_check({"node_id": "664ed9ae-124d-4b27-bb8f-19b99ac2dee1"})        | We will perform an `access_control_check` on node `664ed9ae-124d-4b27-bb8f-19b99ac2dee1` (`/api/Users/1`) to test for unauthorized access or IDOR/BOLA vulnerabilities on user accounts.
           4 | reflected_input_check({"node_id": "ec2839fc-d667-4cfc-becd-b8b068f19d2b"})       | We will perform a reflected input check on the search endpoint (`/rest/products/search?q=test`) to test if user-supplied query parameters are reflected back in the HTTP response body.
           5 | http_probe({"node_id": "fdb93739-d6e5-4349-8085-69528a1345d5"})                  | We need to continue probing discovered endpoint nodes to inspect HTTP responses for potential sensitive data disclosures.
(7 rows)
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
    "scan_id": "72e9acd1-7042-4721-9279-804cf3fe9251",
    "label": "PPP Service (port 3000)",
    "node_type": "ppp_service",
    "is_critical": true,
    "properties": {
      "port": 3000,
      "service": "ppp",
      "evidence_id": "fa70b483-5720-40af-b4fe-42948a5a7ee7"
    },
    "created_at": "2026-10-06T08:35:14.296273"
  },
  "disconnection_impact_score": 0,
  "tie_existed": true,
  "tie_break_reason": "Tie detected: 7 nodes shared maximum disconnection impact score of 0. Selected node '401250ac-77d8-4ab8-9701-51f94c07c552' ('PPP Service (port 3000)') because it was created earliest (2026-10-06T08:35:14.296273)."
}
```

---

## Step 4: Human Review & Invalidation Propagation

Evaluated access control finding edge `94a6623e-d4c3-4529-ab22-804f371bdb79` (`access_control_check:same_session_different_identifier`) on endpoint `/rest/basket/1`.

### Initial Edge Creation Parameters (Phase 18 Adaptive Blending)
- **Raw Evidence Score:** `0.6000`
- **Current Pattern Prior (1 prior refutation):** $w = 0.5, \text{prior} = 0.3333$
- **Blended Stated Confidence:** $0.5 \times 0.60 + 0.5 \times 0.3333 = 0.4667$

### Human Review API Call
`POST http://127.0.0.1:8000/scans/72e9acd1-7042-4721-9279-804cf3fe9251/edges/94a6623e-d4c3-4529-ab22-804f371bdb79/human-review`  
**Body:** `{"decision": "refute", "reviewer": "lead_auditor", "reason": "Manual verification showed unauthenticated 401 response in production environment"}`

### API Response
```json
{
  "edge_id": "94a6623e-d4c3-4529-ab22-804f371bdb79",
  "scan_id": "72e9acd1-7042-4721-9279-804cf3fe9251",
  "decision": "refute",
  "new_status": "human_invalidated",
  "verification_outcome": "HUMAN_INVALIDATED",
  "correction_id": "385a352a-8cf2-442a-a396-d9f476667b27",
  "propagation_result": {
    "invalidated_edge_id": "94a6623e-d4c3-4529-ab22-804f371bdb79",
    "scan_id": "72e9acd1-7042-4721-9279-804cf3fe9251",
    "downstream_nodes_checked": 1,
    "undermined_nodes": [
      "4bff59ed-73d9-44e7-bd0a-722234b7d79d"
    ],
    "still_supported_nodes": []
  }
}
```

### PostgreSQL Database Cross-Check (`human_corrections` table)
```bash
docker exec attackgraph-postgres psql -U attackgraph_user -d attackgraph_db -c "SELECT id, scan_id, target_id, correction_type, notes, created_at FROM human_corrections WHERE scan_id = '72e9acd1-7042-4721-9279-804cf3fe9251';"

                  id                  |               scan_id                |              target_id               |  correction_type  |                                                           notes                                                           |         created_at         
--------------------------------------+--------------------------------------+--------------------------------------+-------------------+---------------------------------------------------------------------------------------------------------------------------+----------------------------
 385a352a-8cf2-442a-a396-d9f476667b27 | 72e9acd1-7042-4721-9279-804cf3fe9251 | 94a6623e-d4c3-4529-ab22-804f371bdb79 | HUMAN_INVALIDATED | Reviewer: lead_auditor. Reason: Manual verification showed unauthenticated 401 response in production environment | 2026-10-06 08:41:29.854061
(1 row)
```

---

## Step 5: Single-Scan Calibration Measurement

Query calibration metrics for scan `72e9acd1-7042-4721-9279-804cf3fe9251`.

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
    {
      "range": "0.0-0.2",
      "count": 0,
      "mean_stated_confidence": null,
      "observed_rate": null,
      "note": "no data in this range"
    },
    {
      "range": "0.2-0.4",
      "count": 0,
      "mean_stated_confidence": null,
      "observed_rate": null,
      "note": "no data in this range"
    },
    {
      "range": "0.4-0.6",
      "count": 1,
      "mean_stated_confidence": 0.4667,
      "observed_rate": 0.0,
      "note": null
    },
    {
      "range": "0.6-0.8",
      "count": 0,
      "mean_stated_confidence": null,
      "observed_rate": null,
      "note": "no data in this range"
    },
    {
      "range": "0.8-1.0",
      "count": 0,
      "mean_stated_confidence": null,
      "observed_rate": null,
      "note": "no data in this range"
    }
  ],
  "sample_size_warning": "Sample size is small (N=1, under 30). Results should be read as illustrative given limited scan volume per project documentation."
}
```

---

## Step 6: Post-Run Learned Pattern Priors

Query global pattern learning state after recording the refutation.

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

### Observation
Following 2 recorded refutations, the learned prior for `access_control_check:same_session_different_identifier` has adaptively updated from initial $0.5000$ to $0.2500$ ($\frac{0+1}{0+2+2} = 0.25$). Any subsequent edge of this pattern key will be initialized with a lower prior-weighted confidence score.
