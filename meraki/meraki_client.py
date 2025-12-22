"""
Lightweight Meraki Dashboard API client used across local automation scripts.

Only the API key is required to authenticate; the organization ID is supplied
per instance because most CRUD workflows are organization scoped.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Iterable, Optional

import requests


logger = logging.getLogger(__name__)


class MerakiAPIError(RuntimeError):
    """Raised when the Meraki Dashboard API returns a non-success response."""

    def __init__(self, status_code: int, message: str, *, payload: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(f"Meraki API error {status_code}: {message}")
        self.status_code = status_code
        self.payload = payload or {}


class MerakiClient:
    """
    Minimal Meraki Dashboard API client that covers common CRUD operations.

    Parameters
    ----------
    api_key:
        Dashboard API key generated in the Meraki portal.
    org_id:
        Organization identifier the requests should target.
    base_url:
        Base URL for the Dashboard API. Defaults to the production v1 endpoint.
    timeout:
        Per-request timeout in seconds.
    max_retries:
        Number of automatic retries to perform on 429 (rate-limited) responses.
    session:
        Optional requests.Session instance to share connection pools.
    """

    def __init__(
        self,
        api_key: str,
        org_id: str,
        *,
        base_url: str = "https://api.meraki.com/api/v1",
        timeout: int = 30,
        max_retries: int = 3,
        session: Optional[requests.Session] = None,
    ) -> None:
        if not api_key:
            raise ValueError("A Meraki API key is required")
        if not org_id:
            raise ValueError("An organization ID is required")

        self.api_key = api_key.strip()
        self.org_id = org_id.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = session or requests.Session()

        self.session.headers.update(
            {
                "X-Cisco-Meraki-API-Key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #
    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        params = params or {}

        for attempt in range(self.max_retries + 1):
            response = self.session.request(
                method,
                url,
                params=params,
                json=json,
                timeout=self.timeout,
            )

            if response.status_code == 429 and attempt < self.max_retries:
                retry_after = int(response.headers.get("Retry-After", "1"))
                retry_after = max(1, retry_after)
                logger.warning("Rate limited by Meraki API, retrying in %s seconds", retry_after)
                time.sleep(retry_after)
                continue

            if response.ok:
                if response.status_code == 204:
                    return None
                if response.headers.get("Content-Type", "").startswith("application/json"):
                    return response.json()
                return response.text

            try:
                error_payload = response.json()
            except ValueError:
                error_payload = {"errors": [response.text]}

            message = ", ".join(error_payload.get("errors", [])) or response.reason
            raise MerakiAPIError(response.status_code, message, payload=error_payload)

        raise MerakiAPIError(429, "Exceeded retry limit after rate limiting")

    # --------------------------------------------------------------------- #
    # Organization scoped helpers
    # --------------------------------------------------------------------- #
    def list_networks(self) -> Any:
        """Return all networks inside the configured organization."""
        return self._request("GET", f"/organizations/{self.org_id}/networks")

    def create_network(
        self,
        name: str,
        product_types: Iterable[str],
        *,
        tags: Optional[Iterable[str]] = None,
        timezone: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Any:
        payload: Dict[str, Any] = {
            "name": name,
            "productTypes": list(product_types),
        }

        if tags:
            payload["tags"] = list(tags)
        if timezone:
            payload["timeZone"] = timezone
        if notes:
            payload["notes"] = notes

        return self._request("POST", f"/organizations/{self.org_id}/networks", json=payload)

    # --------------------------------------------------------------------- #
    # Network scoped helpers
    # --------------------------------------------------------------------- #
    def get_network(self, network_id: str) -> Any:
        """Fetch a single network by ID."""
        return self._request("GET", f"/networks/{network_id}")

    def update_network(self, network_id: str, **updates: Any) -> Any:
        """Apply updates to a network (name, tags, timeZone, notes, etc.)."""
        if not updates:
            raise ValueError("At least one update field must be provided")
        return self._request("PUT", f"/networks/{network_id}", json=updates)

    def delete_network(self, network_id: str) -> None:
        """Delete a network permanently."""
        self._request("DELETE", f"/networks/{network_id}")

    def list_devices(self, network_id: str) -> Any:
        """List every device assigned to a network."""
        return self._request("GET", f"/networks/{network_id}/devices")

    def claim_devices(self, network_id: str, serials: Iterable[str]) -> Any:
        """Claim multiple device serials into the target network."""
        payload = {"serials": list(serials)}
        return self._request("POST", f"/networks/{network_id}/devices/claim", json=payload)

    def remove_devices(self, network_id: str, serials: Iterable[str]) -> None:
        """Remove device serials from a network."""
        for serial in serials:
            self._request("DELETE", f"/networks/{network_id}/devices/{serial}")

    # --------------------------------------------------------------------- #
    # Generic helpers
    # --------------------------------------------------------------------- #
    def raw_request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Execute a raw request against the Meraki API.

        This keeps the convenience of the shared session, retries, and error
        handling while allowing the caller to hit endpoints that do not yet
        have dedicated helpers in this lightweight client.
        """
        if not path.startswith("/"):
            path = f"/{path}"
        return self._request(method.upper(), path, params=params, json=json)

