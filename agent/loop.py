"""
agent/loop.py

LLM function-calling agent loop according to Phase 9 (Section 27, 7, 19).

NOTE ON LLM PROVIDER SUBSTITUTION:
The project specification document specifies "Anthropic API / Claude" as the primary
LLM provider. For practical access and platform availability, we are implementing this
loop against Google's Gemini API (google-generativeai SDK) using models such as
gemini-2.0-flash or gemini-1.5-pro. The architecture remains provider-agnostic because
the decision loop strictly relies on standard structured function-calling / tool-use
capabilities supported natively by Gemini.
"""

import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
from sqlalchemy.orm import Session

from db.models import Scan, Node, Evidence, AgentLog
from agent.tool_schemas import AGENT_TOOLS
from agent.state_summary import summarize_scan_state
from tools.nmap import execute_nmap_scan
from tools.ffuf import execute_ffuf_scan
from tools.http_probe import execute_http_probe
from tools.access_control_check import execute_access_control_check
from tools.reflected_input_check import execute_reflected_input_check

load_dotenv()

DEFAULT_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


def _get_executed_tool_pairs(scan_id: str, db: Session) -> set:
    """Returns set of (tool_name, node_id) tuples executed so far in this scan."""
    evidence_rows = db.query(Evidence).filter(Evidence.scan_id == scan_id).all()
    executed = set()
    for ev in evidence_rows:
        executed.add((ev.tool_name, ev.node_id))
    return executed


def execute_agent_step(
    scan_id: str,
    db: Session,
    step_number: int = 1,
    model_name: str = DEFAULT_MODEL_NAME
) -> Dict[str, Any]:
    """
    Executes a SINGLE step of the agent decision loop:
    1. Summarizes current scan state (nodes, edges, uninvestigated endpoints).
    2. Calls Gemini with tool schemas.
    3. Validates proposed tool call (cross-scan node scoping, duplicate check).
    4. Executes real tool function or records rejection.
    5. Records thought/action/observation in agent_log.
    """
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise ValueError(f"Scan with ID '{scan_id}' not found")

    state_summary = summarize_scan_state(scan_id, db)
    executed_pairs = _get_executed_tool_pairs(scan_id, db)

    system_instruction = (
        "You are an automated security analysis agent operating under strict authorization rules. "
        "Your task is to iteratively inspect target nodes, discover endpoints, probe services, and test for "
        "conservative security observations (access control and reflected input) until all useful checks "
        "on discovered nodes are exhausted.\n\n"
        "RULES:\n"
        "1. Only target node_ids belonging to the current scan provided in the state summary.\n"
        "2. Do NOT re-run a tool on a node_id if that exact check has already been executed.\n"
        "3. When all pending checks on discovered endpoints are complete, call 'no_further_action'.\n"
        "4. Output clear reasoning before invoking any tool."
    )

    prompt = (
        f"CURRENT SCAN STATE:\n"
        f"{json.dumps(state_summary, indent=2)}\n\n"
        f"ALREADY EXECUTED (tool_name, node_id) PAIRS:\n"
        f"{[f'{t}:{n}' for t, n in executed_pairs]}\n\n"
        f"Select the next security check tool to run, or call 'no_further_action' if complete."
    )

    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        genai.configure(api_key=api_key)

    model = genai.GenerativeModel(
        model_name=model_name,
        tools=AGENT_TOOLS,
        system_instruction=system_instruction,
    )

    response = model.generate_content(prompt)

    # Extract function call or thought from response
    function_call = None
    thought_text = ""

    if response.candidates:
        candidate = response.candidates[0]
        for part in candidate.content.parts:
            if part.text:
                thought_text += part.text + "\n"
            if part.function_call:
                function_call = part.function_call

    if not function_call:
        action_str = "no_tool_call"
        observation_str = "LLM did not propose a function call."
        log_entry = AgentLog(
            scan_id=scan_id,
            step_number=step_number,
            thought=thought_text.strip() or "No explicit reasoning provided.",
            action=action_str,
            observation=observation_str,
            timestamp=datetime.utcnow(),
        )
        db.add(log_entry)
        db.commit()
        return {
            "step": step_number,
            "accepted": False,
            "reason": observation_str,
            "tool": None,
            "result": None,
            "stop": True,
        }

    tool_name = function_call.name
    args = dict(function_call.args) if function_call.args else {}
    target_node_id = args.get("node_id")

    action_str = f"{tool_name}({json.dumps(args)})"

    # --- SAFETY CHECK 1: Terminal tool handle ---
    if tool_name == "no_further_action":
        reason = args.get("reason", "Investigation completed.")
        log_entry = AgentLog(
            scan_id=scan_id,
            step_number=step_number,
            thought=thought_text.strip(),
            action=action_str,
            observation=f"Agent signaled completion: {reason}",
            timestamp=datetime.utcnow(),
        )
        db.add(log_entry)
        db.commit()
        return {
            "step": step_number,
            "accepted": True,
            "tool": tool_name,
            "reason": reason,
            "result": "completed",
            "stop": True,
        }

    # --- SAFETY CHECK 2: Cross-scan Node Scoping ---
    if target_node_id:
        target_node = db.query(Node).filter(Node.id == target_node_id).first()
        if not target_node:
            rejection_reason = f"Security Violation / Invalid Node: Node '{target_node_id}' does not exist."
            log_entry = AgentLog(
                scan_id=scan_id,
                step_number=step_number,
                thought=thought_text.strip(),
                action=action_str,
                observation=f"REJECTED: {rejection_reason}",
                timestamp=datetime.utcnow(),
            )
            db.add(log_entry)
            db.commit()
            return {
                "step": step_number,
                "accepted": False,
                "reason": rejection_reason,
                "tool": tool_name,
                "node_id": target_node_id,
                "stop": False,
            }
        if target_node.scan_id != scan_id:
            rejection_reason = f"Security Violation: Node '{target_node_id}' belongs to scan '{target_node.scan_id}', not current scan '{scan_id}'."
            log_entry = AgentLog(
                scan_id=scan_id,
                step_number=step_number,
                thought=thought_text.strip(),
                action=action_str,
                observation=f"REJECTED: {rejection_reason}",
                timestamp=datetime.utcnow(),
            )
            db.add(log_entry)
            db.commit()
            return {
                "step": step_number,
                "accepted": False,
                "reason": rejection_reason,
                "tool": tool_name,
                "node_id": target_node_id,
                "stop": False,
            }

    # --- SAFETY CHECK 3: Duplicate Action Guardrail ---
    if (tool_name, target_node_id) in executed_pairs:
        rejection_reason = f"Duplicate Action: Pair ({tool_name}, {target_node_id}) has already been executed in scan '{scan_id}'."
        log_entry = AgentLog(
            scan_id=scan_id,
            step_number=step_number,
            thought=thought_text.strip(),
            action=action_str,
            observation=f"REJECTED: {rejection_reason}",
            timestamp=datetime.utcnow(),
        )
        db.add(log_entry)
        db.commit()
        return {
            "step": step_number,
            "accepted": False,
            "reason": rejection_reason,
            "tool": tool_name,
            "node_id": target_node_id,
            "stop": False,
        }

    # --- DISPATCH REAL TOOL EXECUTION ---
    tool_result = None
    try:
        if tool_name == "nmap_scan":
            tool_result = execute_nmap_scan(scan_id, db)
        elif tool_name == "ffuf_scan":
            tool_result = execute_ffuf_scan(scan_id, db)
        elif tool_name == "http_probe":
            method = args.get("method", "GET")
            tool_result = execute_http_probe(scan_id, target_node_id, db, method=method)
        elif tool_name == "access_control_check":
            tool_result = execute_access_control_check(scan_id, target_node_id, db)
        elif tool_name == "reflected_input_check":
            tool_result = execute_reflected_input_check(scan_id, target_node_id, db)
        else:
            raise ValueError(f"Unknown tool name '{tool_name}' proposed by LLM.")

        observation_str = f"SUCCESS: Executed {tool_name}."
        log_entry = AgentLog(
            scan_id=scan_id,
            step_number=step_number,
            thought=thought_text.strip(),
            action=action_str,
            observation=observation_str,
            timestamp=datetime.utcnow(),
        )
        db.add(log_entry)
        db.commit()

        return {
            "step": step_number,
            "accepted": True,
            "tool": tool_name,
            "node_id": target_node_id,
            "result_summary": observation_str,
            "stop": False,
        }
    except Exception as e:
        error_msg = str(e)
        observation_str = f"ERROR: Tool execution failed: {error_msg}"

        # Record Evidence row so future steps treat this (tool_name, node_id) pair as attempted
        failed_evidence = Evidence(
            scan_id=scan_id,
            node_id=target_node_id,
            tool_name=tool_name,
            raw_output=f"Tool call failed: {error_msg}",
            parsed_findings={"error": error_msg, "attempted": True},
            timestamp=datetime.utcnow(),
        )
        db.add(failed_evidence)

        log_entry = AgentLog(
            scan_id=scan_id,
            step_number=step_number,
            thought=thought_text.strip(),
            action=action_str,
            observation=observation_str,
            timestamp=datetime.utcnow(),
        )
        db.add(log_entry)
        db.commit()

        return {
            "step": step_number,
            "accepted": False,
            "reason": error_msg,
            "tool": tool_name,
            "node_id": target_node_id,
            "stop": False,
        }



def run_agent_loop(scan_id: str, db: Session, max_steps: int = 15, model_name: str = DEFAULT_MODEL_NAME) -> Dict[str, Any]:
    """
    Runs the LLM function-calling agent loop until complete, max_steps reached,
    or no further action is indicated.
    """
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise ValueError(f"Scan with ID '{scan_id}' not found")

    steps_taken = []
    scan.status = "AGENT_LOOP_RUNNING"
    db.commit()

    for step in range(1, max_steps + 1):
        step_res = execute_agent_step(scan_id, db, step_number=step, model_name=model_name)
        steps_taken.append(step_res)

        if step_res.get("stop", False):
            break

    scan.status = "AGENT_LOOP_COMPLETED"
    db.commit()

    final_state = summarize_scan_state(scan_id, db)
    return {
        "scan_id": scan_id,
        "total_steps": len(steps_taken),
        "max_steps": max_steps,
        "steps": steps_taken,
        "final_state": final_state,
    }
