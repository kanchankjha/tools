import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional


class MerakiHttpError(RuntimeError):
    def __init__(self, status: int, message: str, body: Optional[str] = None):
        super().__init__(message)
        self.status = status
        self.body = body


class MerakiClient:
    """
    Minimal Meraki Dashboard API client using only the standard library.
    Intended for backup/restore automation without third-party dependencies.
    """

    def __init__(
        self,
        api_key: str,
        org_id: str,
        base_url: str = "https://api.meraki.com/api/v1",
        timeout: int = 20,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        user_agent: str = "meraki-snapshot/0.1",
    ):
        self.api_key = api_key
        self.org_id = org_id
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.user_agent = user_agent

    # ---- HTTP helpers -------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        allow_404: bool = False,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")

        headers = {
            "X-Cisco-Meraki-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }

        attempt = 0
        while True:
            attempt += 1
            request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                    content = resp.read()
                    if not content:
                        return None
                    return json.loads(content.decode("utf-8"))
            except urllib.error.HTTPError as exc:
                status = exc.code
                body = exc.read().decode("utf-8") if exc.fp else ""
                if allow_404 and status == 404:
                    return None
                if status == 429 or 500 <= status < 600:
                    if attempt <= self.max_retries:
                        retry_after = float(exc.headers.get("Retry-After", self.backoff_seconds))
                        time.sleep(retry_after)
                        continue
                raise MerakiHttpError(status, f"HTTP {status} for {method} {path}", body=body) from exc
            except urllib.error.URLError as exc:  # network hiccups
                if attempt <= self.max_retries:
                    time.sleep(self.backoff_seconds * attempt)
                    continue
                raise MerakiHttpError(-1, f"Network error for {method} {path}: {exc}") from exc

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None, allow_404: bool = False) -> Any:
        return self._request("GET", path, params=params, allow_404=allow_404)

    def _put(self, path: str, payload: Dict[str, Any]) -> Any:
        return self._request("PUT", path, payload=payload)

    def _post(self, path: str, payload: Dict[str, Any]) -> Any:
        return self._request("POST", path, payload=payload)

    # ---- Org / network discovery -------------------------------------
    def get_organization(self) -> Dict[str, Any]:
        return self._get(f"/organizations/{self.org_id}")

    def list_networks(self) -> List[Dict[str, Any]]:
        return self._get(f"/organizations/{self.org_id}/networks", params={"perPage": 1000})

    def list_devices(self, network_id: str) -> List[Dict[str, Any]]:
        return self._get(f"/networks/{network_id}/devices", params={"perPage": 1000})

    def list_org_admins(self) -> List[Dict[str, Any]]:
        return self._get(f"/organizations/{self.org_id}/admins")

    def list_config_templates(self) -> List[Dict[str, Any]]:
        return self._get(f"/organizations/{self.org_id}/configTemplates")

    # ---- Configuration fetch helpers ---------------------------------
    def fetch_appliance_config(self, network_id: str) -> Dict[str, Any]:
        return {
            "settings": self._get(f"/networks/{network_id}/appliance/settings", allow_404=True),
            "vlans": self._get(f"/networks/{network_id}/appliance/vlans", allow_404=True),
            "firewall_l3": self._get(f"/networks/{network_id}/appliance/firewall/l3FirewallRules", allow_404=True),
            "firewall_l7": self._get(f"/networks/{network_id}/appliance/firewall/l7FirewallRules", allow_404=True),
            "content_filtering": self._get(
                f"/networks/{network_id}/appliance/contentFiltering/settings", allow_404=True
            ),
            "static_routes": self._get(f"/networks/{network_id}/appliance/staticRoutes", allow_404=True),
        }

    def fetch_switch_config(self, network_id: str) -> Dict[str, Any]:
        return {
            "stp": self._get(f"/networks/{network_id}/switch/stp", allow_404=True),
            "dhcp_server_policy": self._get(f"/networks/{network_id}/switch/dhcpServerPolicy", allow_404=True),
            "routing_interfaces": self._get(f"/networks/{network_id}/switch/routing/interfaces", allow_404=True),
            "switch_ports": self._get(f"/networks/{network_id}/switch/ports", allow_404=True),
        }

    def fetch_wireless_config(self, network_id: str) -> Dict[str, Any]:
        return {
            "ssids": self._get(f"/networks/{network_id}/wireless/ssids", allow_404=True),
            "rf_profiles": self._get(f"/networks/{network_id}/wireless/rfProfiles", allow_404=True),
            "firewall_l3": self._get(f"/networks/{network_id}/wireless/firewall/l3FirewallRules", allow_404=True),
        }

    def fetch_camera_config(self, network_id: str) -> Dict[str, Any]:
        return {"video_settings": self._get(f"/networks/{network_id}/camera/video/settings", allow_404=True)}

    def collect_network_config(self, network_id: str, product_types: List[str]) -> Dict[str, Any]:
        config: Dict[str, Any] = {}
        if "appliance" in product_types or "appliance" in [p.lower() for p in product_types]:
            config["appliance"] = self.fetch_appliance_config(network_id)
        if "switch" in product_types or "switch" in [p.lower() for p in product_types]:
            config["switch"] = self.fetch_switch_config(network_id)
        if "wireless" in product_types or "wireless" in [p.lower() for p in product_types]:
            config["wireless"] = self.fetch_wireless_config(network_id)
        if "camera" in product_types or "camera" in [p.lower() for p in product_types]:
            config["camera"] = self.fetch_camera_config(network_id)
        return config

    # ---- Configuration apply stubs -----------------------------------
    def apply_network_config(self, network_id: str, config: Dict[str, Any]) -> List[str]:
        """
        Apply a subset of configuration back to the network. This is intentionally conservative:
        it returns a list of operations performed, which keeps restore dry-run friendly.
        """
        operations: List[str] = []

        appliance = config.get("appliance")
        if appliance and appliance.get("vlans") is not None:
            # Actual PUT endpoints exist per VLAN; for brevity, this is a placeholder.
            operations.append("appliance.vlans planned")

        switch_cfg = config.get("switch")
        if switch_cfg and switch_cfg.get("switch_ports") is not None:
            operations.append("switch.ports planned")

        wireless_cfg = config.get("wireless")
        if wireless_cfg and wireless_cfg.get("ssids") is not None:
            operations.append("wireless.ssids planned")

        camera_cfg = config.get("camera")
        if camera_cfg and camera_cfg.get("video_settings") is not None:
            operations.append("camera.video planned")

        return operations
