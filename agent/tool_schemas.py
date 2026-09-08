from google.generativeai.types import FunctionDeclaration, Tool

# Tool declarations for Gemini API following Google Generative AI SDK function declaration schemas

nmap_scan_declaration = FunctionDeclaration(
    name="nmap_scan",
    description="Executes an Nmap port scan against the target URL of the scan to discover open ports and web services.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "scan_id": {
                "type": "STRING",
                "description": "ID of the current scan."
            }
        },
        "required": ["scan_id"]
    }
)

ffuf_scan_declaration = FunctionDeclaration(
    name="ffuf_scan",
    description="Executes a directory/endpoint fuzzing scan (ffuf) against the target URL to discover endpoints.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "scan_id": {
                "type": "STRING",
                "description": "ID of the current scan."
            }
        },
        "required": ["scan_id"]
    }
)

http_probe_declaration = FunctionDeclaration(
    name="http_probe",
    description="Executes a targeted HTTP GET/POST probe against a specific discovered endpoint node and inspects response for secrets.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "node_id": {
                "type": "STRING",
                "description": "ID of the discovered endpoint node to probe."
            },
            "method": {
                "type": "STRING",
                "description": "HTTP method to use (e.g. GET, POST). Defaults to GET."
            }
        },
        "required": ["node_id"]
    }
)

access_control_check_declaration = FunctionDeclaration(
    name="access_control_check",
    description="Tests whether modifying an identifier in an endpoint URL reveals unauthorized user data (IDOR / BOLA check).",
    parameters={
        "type": "OBJECT",
        "properties": {
            "node_id": {
                "type": "STRING",
                "description": "ID of the endpoint node with query parameter or path identifier."
            }
        },
        "required": ["node_id"]
    }
)

reflected_input_check_declaration = FunctionDeclaration(
    name="reflected_input_check",
    description="Inserts a harmless marker into a query parameter on an endpoint node to test if user input is reflected in response body.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "node_id": {
                "type": "STRING",
                "description": "ID of the endpoint node containing a query parameter to test for reflection."
            }
        },
        "required": ["node_id"]
    }
)

no_further_action_declaration = FunctionDeclaration(
    name="no_further_action",
    description="Signals that the agent has completed all useful investigation and no further checks or scans are required.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "reason": {
                "type": "STRING",
                "description": "Explanation of why investigation is complete."
            }
        },
        "required": ["reason"]
    }
)

AGENT_TOOLS = [
    Tool(
        function_declarations=[
            nmap_scan_declaration,
            ffuf_scan_declaration,
            http_probe_declaration,
            access_control_check_declaration,
            reflected_input_check_declaration,
            no_further_action_declaration,
        ]
    )
]
