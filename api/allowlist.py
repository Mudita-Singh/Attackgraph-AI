from pathlib import Path
from urllib.parse import urlparse
import yaml
from typing import List, Dict, Any, Optional

ALLOWLIST_FILE = Path(__file__).parent.parent / "config" / "allowlist.yaml"

class AllowlistValidator:
    def __init__(self, config_path: Path = ALLOWLIST_FILE):
        self.config_path = config_path
        self.allowed_targets: List[Dict[str, Any]] = []
        self.load_allowlist()

    def load_allowlist(self):
        if not self.config_path.exists():
            raise FileNotFoundError(f"Allowlist configuration file not found at: {self.config_path}")
        
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            self.allowed_targets = data.get("allowed_targets", [])

    def is_target_allowed(self, target_url: str) -> bool:
        """
        Server-side validation check.
        Normalizes target_url and verifies whether host and port match the strict allowlist configuration.
        Safely catches all URL parsing/port exceptions and returns False (HTTP 403) instead of raising 500.
        Rejects path traversal, embedded authority credentials, and malformed hosts.
        """
        if not target_url or not isinstance(target_url, str):
            return False

        try:
            # 1. Reject authority trickery (e.g. user:pass@evil.com or localhost:3000@evil.com)
            if "@" in target_url.split("/")[2] if "://" in target_url else "@" in target_url.split("/")[0]:
                return False

            # 2. Reject path traversal attempts (e.g. /../../etc/passwd or %2e%2e)
            url_lower = target_url.lower()
            if ".." in url_lower or "%2e%2e" in url_lower or "\\" in url_lower:
                return False

            # 3. Parse URL safely
            parsed = urlparse(target_url if "://" in target_url else f"http://{target_url}")

            # Must use http or https
            if parsed.scheme not in ("http", "https"):
                return False

            # Reject embedded userinfo
            if parsed.username or parsed.password:
                return False

            # Safely extract host and port
            target_host = (parsed.hostname or "").lower()
            if not target_host:
                return False

            try:
                target_port = parsed.port
            except ValueError:
                # E.g. port could not be cast to integer (e.g., "3000.evil.com")
                return False

            if target_port is None:
                target_port = 443 if parsed.scheme == "https" else 80

            # 4. Check against allowlist entries
            for target in self.allowed_targets:
                allowed_host_main = (target.get("host") or "").lower()
                allowed_port_main = target.get("port")

                if allowed_host_main and allowed_port_main:
                    if target_host == allowed_host_main and target_port == allowed_port_main:
                        return True

                for url in target.get("urls", []):
                    try:
                        parsed_allowed = urlparse(url)
                        allowed_host = (parsed_allowed.hostname or "").lower()
                        allowed_port = parsed_allowed.port or (443 if parsed_allowed.scheme == "https" else 80)
                        if target_host == allowed_host and target_port == allowed_port:
                            return True
                    except Exception:
                        continue

            return False

        except Exception:
            # Any unexpected parsing error returns False (403 Forbidden), never 500
            return False

# Global instance
allowlist_validator = AllowlistValidator()
