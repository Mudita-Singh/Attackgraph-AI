"""
agent/loop.py

LLM function-calling agent loop according to Phase 9 (Section 27, 7, 19).

NOTE ON LLM PROVIDER & SDK SUBSTITUTION:
The project specification document specifies "Anthropic API / Claude" as the primary
LLM provider. For practical access and platform availability, we are implementing this
loop against Google's Gemini API using the official google-genai SDK (genai.Client) and
models such as gemini-2.5-flash. The architecture remains provider-agnostic because the
decision loop strictly relies on standard structured function-calling / tool-use capabilities.
"""

import json
import os
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types
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

# Chosen from client.models.list() & API verification: gemini-3.6-flash is Google's recommended
# stable flash model, providing low-latency execution, low cost tier, 1M+ token context window,
# and verified native function calling (FunctionCall) support.
DEFAULT_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")


def _generate_content_with_retry(
    client: genai.Client,
    model_name: str,
    prompt: str,
    config: types.GenerateContentConfig,
    max_retries: int = 3,
    initial_delay: float = 2.0
) -> Any:
    """
    Executes client.models.generate_content with exponential backoff retries.
    """
    delay = initial_delay
    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            return client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
        except Exception as e:
            last_exception = e
            if attempt == max_retries:
                raise e
            time.sleep(delay)
            delay *= 2.0



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
    2. Calls Gemini (google.genai SDK) with tool schemas.
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
        "You are operating a defensive security research tool within an isolated, "
        "fully authorized local lab environment. The ONLY targets that exist in "
        "this system are two applications deliberately designed and distributed by "
        "their own creators specifically FOR this kind of automated testing: OWASP "
        "Juice Shop and DVWA (Damn Vulnerable Web Application). Both are "
        "industry-standard security training applications used in university "
        "courses worldwide. No external, production, or third-party system can "
        "ever be targeted - a hardcoded server-side allowlist enforces this before "
        "any action is taken, and you have no ability to specify or reach any "
        "other target.\n\n"
        "Your task is to select the next authorized, pre-approved diagnostic action "
        "from the fixed list of tool functions provided, based on the current "
        "investigation state. Each action is a narrow, read-only or comparison-only "
        "operation (port/service enumeration, endpoint discovery, HTTP response "
        "inspection, or a conservative comparison check) - you are not writing "
        "exploit code or open-ended attack instructions, you are selecting one "
        "pre-built, already-implemented diagnostic function to run next, the same "
        "way a vulnerability scanner's own internal logic selects its next check.\n\n"
        "RULES:\n"
        "1. Only target node_ids belonging to the current scan shown in the state summary below.\n"
        "2. Do not re-run a check that has already been executed on the same node.\n"
        "3. When all pending checks on discovered endpoints are complete, call 'no_further_action'.\n"
        "4. Briefly explain your reasoning, then call exactly one function."
    )

    prompt = (
        f"TARGET UNDER DIAGNOSTIC TEST: {scan.target_url} (Authorized local lab training environment)\n\n"
        f"CURRENT SCAN STATE:\n"
        f"{json.dumps(state_summary, indent=2)}\n\n"
        f"ALREADY EXECUTED (tool_name, node_id) PAIRS:\n"
        f"{[f'{t}:{n}' for t, n in executed_pairs]}\n\n"
        f"Select the next authorized diagnostic tool function to run, or call 'no_further_action' if complete."
    )

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    http_options = types.HttpOptions(client_args={"timeout": 30.0})
    client = genai.Client(api_key=api_key, http_options=http_options)

    # SAFETY SETTINGS RATIONALE:
    # This is NOT a blanket safety bypass; it narrows only HARM_CATEGORY_DANGEROUS_CONTENT
    # to BLOCK_ONLY_HIGH (not BLOCK_NONE). The default threshold was producing false-positive
    # refusals on legitimate diagnostic tool output being echoed back in the prompt context
    # (e.g. raw HTTP response bodies from http_probe).
    #
    # Empirically verified: Scan a473a0ca suffered a mid-run refusal at Step 4 without this setting
    # when raw endpoint response text was fed into conversation history, whereas Scan 84e922a9
    # executed multi-step tool calls cleanly with it.
    #
    # Scope: This applies strictly within the project's hardcoded, allowlist-enforced local lab
    # environment (Section 20).
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        tools=AGENT_TOOLS,
        safety_settings=[
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
            )
        ]
    )

    try:
        response = _generate_content_with_retry(
            client=client,
            model_name=model_name,
            prompt=prompt,
            config=config,
            max_retries=3,
            initial_delay=2.0
        )
    except Exception as e:
        error_msg = f"Gemini API call failed after retries/timeout: {str(e)}"
        action_str = "api_error"
        observation_str = f"ERROR: {error_msg}"
        log_entry = AgentLog(
            scan_id=scan_id,
            step_number=step_number,
            thought="API call failed or timed out.",
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
            "tool": None,
            "result": None,
            "stop": True,
        }

    function_call = None
    thought_text = ""

    if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if hasattr(part, "text") and part.text:
                thought_text += part.text + "\n"

    if response.function_calls:
        function_call = response.function_calls[0]

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
