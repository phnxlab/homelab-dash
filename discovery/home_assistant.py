import ipaddress
import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from websocket import WebSocketException, create_connection

from django.conf import settings

from dashboard.models import DiscoveredDevice


class HomeAssistantError(Exception):
    """Raised when the Home Assistant API cannot be queried or parsed."""


@dataclass
class SyncSummary:
    discovered: int = 0
    updated: int = 0
    skipped: int = 0


class HomeAssistantProvider:
    """Import network-aware devices from Home Assistant's device registry."""

    states_path = "/api/states"

    def __init__(self, base_url=None, token=None, timeout=None, opener=urlopen, websocket_factory=create_connection):
        self.base_url = (base_url or settings.HOME_ASSISTANT_URL).rstrip("/")
        self.token = token or settings.HOME_ASSISTANT_TOKEN
        self.timeout = timeout or settings.HOME_ASSISTANT_TIMEOUT_SECONDS
        self.opener = opener
        self.websocket_factory = websocket_factory

    def sync(self):
        if not self.base_url or not self.token:
            raise HomeAssistantError("HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN must be configured.")

        registry = self._get_websocket_result("config/device_registry/list")
        entity_registry = self._get_websocket_result("config/entity_registry/list")
        states = self._get_json(self.states_path)
        state_attributes = self._state_attributes_by_device(states, entity_registry)
        summary = SyncSummary()

        for device in registry:
            normalized = self._normalize_device(device, state_attributes)
            if normalized is None:
                summary.skipped += 1
                continue

            _, created = DiscoveredDevice.objects.update_or_create(
                source=DiscoveredDevice.Source.HOME_ASSISTANT,
                external_id=normalized["external_id"],
                defaults=normalized,
            )
            summary.discovered += 1
            summary.updated += int(not created)
        return summary

    def _get_json(self, path):
        request = Request(
            f"{self.base_url}{path}",
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            raise HomeAssistantError(f"Home Assistant request failed for {path}: {error}") from error

    def _get_websocket_result(self, command):
        try:
            with self.websocket_factory(self._websocket_url(), timeout=self.timeout) as websocket:
                auth_required = json.loads(websocket.recv())
                if auth_required.get("type") != "auth_required":
                    raise HomeAssistantError("Home Assistant did not begin WebSocket authentication.")
                websocket.send(json.dumps({"type": "auth", "access_token": self.token}))
                authentication = json.loads(websocket.recv())
                if authentication.get("type") != "auth_ok":
                    raise HomeAssistantError(f"Home Assistant WebSocket authentication failed: {authentication.get('message', 'unknown error')}")
                websocket.send(json.dumps({"id": 1, "type": command}))
                response = json.loads(websocket.recv())
        except (OSError, TimeoutError, ValueError, WebSocketException) as error:
            raise HomeAssistantError(f"Home Assistant WebSocket request failed for {command}: {error}") from error

        if response.get("type") != "result" or response.get("id") != 1 or not response.get("success"):
            message = response.get("error", {}).get("message", "unexpected response")
            raise HomeAssistantError(f"Home Assistant WebSocket command {command} failed: {message}")
        return response.get("result", [])

    def _websocket_url(self):
        if self.base_url.startswith("https://"):
            return f"wss://{self.base_url.removeprefix('https://')}/api/websocket"
        if self.base_url.startswith("http://"):
            return f"ws://{self.base_url.removeprefix('http://')}/api/websocket"
        raise HomeAssistantError("HOME_ASSISTANT_URL must start with http:// or https://.")

    @staticmethod
    def _state_attributes_by_device(states, entity_registry):
        device_ids_by_entity = {entry.get("entity_id"): entry.get("device_id") for entry in entity_registry}
        attributes = {}
        for state in states:
            device_id = device_ids_by_entity.get(state.get("entity_id"))
            if device_id:
                attributes.setdefault(device_id, {}).update(state.get("attributes", {}))
        return attributes

    @classmethod
    def _normalize_device(cls, device, state_attributes):
        device_id = device.get("id")
        if not device_id:
            return None

        attributes = state_attributes.get(device_id, {})
        connections = device.get("connections", [])
        ip_address = cls._connection_value(connections, "ip") or attributes.get("ip_address")
        if not ip_address:
            return None
        try:
            ip_address = str(ipaddress.ip_address(ip_address))
        except ValueError:
            return None

        mac_address = cls._connection_value(connections, "mac") or attributes.get("mac_address", "")
        return {
            "external_id": device_id,
            "hostname": device.get("name_by_user") or device.get("name") or attributes.get("friendly_name", ""),
            "ip_address": ip_address,
            "mac_address": mac_address,
            "is_online": True,
            "metadata": {
                "manufacturer": device.get("manufacturer", ""),
                "model": device.get("model", ""),
                "area_id": device.get("area_id"),
                "via_device_id": device.get("via_device_id"),
            },
        }

    @staticmethod
    def _connection_value(connections, connection_type):
        for item in connections:
            if len(item) == 2 and item[0] == connection_type:
                return item[1]
        return ""