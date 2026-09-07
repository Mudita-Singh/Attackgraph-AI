import re
from typing import List, Dict, Any

class SecretPattern:
    def __init__(self, key: str, name: str, pattern: str, confidence: float, description: str):
        self.key = key
        self.name = name
        self.pattern = re.compile(pattern, re.MULTILINE)
        self.confidence = confidence
        self.description = description

# Documented pattern list covered in secret detection
# Scope: Structural signatures for high-value secrets (AWS keys, JWTs, DB connection URLs, API keys, password assignments).
# Out of Scope: Random high-entropy strings without context, standalone common words ("key", "token", "pass") without assignments.
SECRET_PATTERNS: List[SecretPattern] = [
    SecretPattern(
        key="aws_access_key",
        name="AWS Access Key ID",
        pattern=r"\b(AKIA[0-9A-Z]{16})\b",
        confidence=0.95,
        description="Matched structural AWS Access Key ID format (AKIA + 16 alphanumeric characters)"
    ),
    SecretPattern(
        key="jwt_token",
        name="JWT Authentication Token",
        pattern=r"\b(eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})\b",
        confidence=0.90,
        description="Matched JSON Web Token (JWT) three-part dot-separated base64url format"
    ),
    SecretPattern(
        key="database_url",
        name="Database Connection String",
        pattern=r"\b((?:postgres|postgresql|mysql|mongodb(?:\+srv)?|redis)://[A-Za-z0-9_.~%-]+:[^@\s'\"]+@[A-Za-z0-9_.-]+(?::\d+)?/[A-Za-z0-9_.~%-]+)\b",
        confidence=0.85,
        description="Matched Database Connection URL scheme with embedded credentials"
    ),
    SecretPattern(
        key="api_key_assignment",
        name="API Key Assignment",
        pattern=r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|secret[_-]?key)\s*[:=]\s*[\"']([A-Za-z0-9_\-]{16,})[\"']",
        confidence=0.75,
        description="Matched API key or access token key-value assignment in JS/JSON"
    ),
    SecretPattern(
        key="generic_secret_assignment",
        name="Password/Secret Assignment",
        pattern=r"(?i)\b(?:password|passwd|pwd|db_pass)\s*[:=]\s*[\"']([^\"'\s]{6,})[\"']",
        confidence=0.70,
        description="Matched password or secret key-value assignment in JS/JSON"
    )
]

def extract_secrets_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Scans response body text against documented secret patterns.
    Returns list of match dicts with key, name, match_preview, confidence, and description.
    """
    if not text:
        return []

    results: List[Dict[str, Any]] = []
    seen_matches = set()

    for p in SECRET_PATTERNS:
        for match in p.pattern.finditer(text):
            # Capture full match or first capture group if defined
            val = match.group(1) if match.groups() else match.group(0)
            if not val or val in seen_matches:
                continue

            seen_matches.add(val)
            # Create a redacted/preview version of secret for labels/logs
            if len(val) > 10:
                preview = f"{val[:4]}...{val[-4:]}"
            else:
                preview = f"{val[:2]}***"

            results.append({
                "pattern_key": p.key,
                "name": p.name,
                "raw_match": val,
                "match_preview": preview,
                "confidence": p.confidence,
                "description": p.description
            })

    return results
