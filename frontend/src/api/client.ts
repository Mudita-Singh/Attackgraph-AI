import type { Scan, GraphData, Evidence, AgentLog, HumanReviewResponse, ReplayEvent, CalibrationReport } from '../types';

const API_BASE_URL = 'http://127.0.0.1:8000';

export async function fetchScans(): Promise<Scan[]> {
  const res = await fetch(`${API_BASE_URL}/scans`);
  if (!res.ok) {
    throw new Error(`Failed to fetch scans: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchGlobalCalibration(): Promise<CalibrationReport> {
  const res = await fetch(`${API_BASE_URL}/calibration`);
  if (!res.ok) {
    throw new Error(`Failed to fetch global calibration: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchScanCalibration(scanId: string): Promise<CalibrationReport> {
  const res = await fetch(`${API_BASE_URL}/scans/${scanId}/calibration`);
  if (!res.ok) {
    throw new Error(`Failed to fetch scan calibration for ${scanId}: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchScanGraph(scanId: string): Promise<GraphData> {
  const res = await fetch(`${API_BASE_URL}/scans/${scanId}/graph`);
  if (!res.ok) {
    throw new Error(`Failed to fetch graph for scan ${scanId}: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchReplayEvents(scanId: string): Promise<ReplayEvent[]> {
  const res = await fetch(`${API_BASE_URL}/scans/${scanId}/replay`);
  if (!res.ok) {
    throw new Error(`Failed to fetch replay events for scan ${scanId}: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchNodeEvidence(scanId: string, nodeId: string): Promise<Evidence[]> {
  const res = await fetch(`${API_BASE_URL}/scans/${scanId}/nodes/${nodeId}/evidence`);
  if (!res.ok) {
    throw new Error(`Failed to fetch evidence for node ${nodeId}: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchAgentLog(scanId: string): Promise<AgentLog[]> {
  const res = await fetch(`${API_BASE_URL}/scans/${scanId}/agent-log`);
  if (!res.ok) {
    throw new Error(`Failed to fetch agent log for scan ${scanId}: ${res.statusText}`);
  }
  return res.json();
}

export async function submitHumanReview(
  scanId: string,
  edgeId: string,
  decision: 'confirm' | 'refute',
  reviewer: string = 'human_reviewer',
  reason: string = 'Reviewed via frontend inspector'
): Promise<HumanReviewResponse> {
  const res = await fetch(`${API_BASE_URL}/scans/${scanId}/edges/${edgeId}/human-review`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      decision,
      reviewer,
      reason,
    }),
  });
  if (!res.ok) {
    throw new Error(`Failed to submit human review: ${res.statusText}`);
  }
  return res.json();
}

export async function reverifyEdge(scanId: string, edgeId: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/scans/${scanId}/edges/${edgeId}/reverify`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new Error(errBody.detail || `Re-verification failed with status ${res.status}`);
  }
  return res.json();
}

export async function runAgent(scanId: string, maxSteps: number = 15): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/scans/${scanId}/agent/run?max_steps=${maxSteps}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new Error(errBody.detail || `Agent execution stopped: status ${res.status}`);
  }
  return res.json();
}

export async function createScan(targetUrl: string): Promise<Scan> {
  const res = await fetch(`${API_BASE_URL}/scans`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ target_url: targetUrl }),
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new Error(errBody.detail || `Failed to create scan for ${targetUrl}`);
  }
  return res.json();
}


