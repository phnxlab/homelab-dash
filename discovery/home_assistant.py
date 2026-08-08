import ipaddress
import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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

    device_registry_path = "/api/config/device_registry/list"
    states_path = "/api/states"

    def __init__(self, base_url=None, token=None, timeout=None, opener=urlopen):
        self.base_url = (base_url or settings.HOME_ASSISTANT_URL).rstrip("/")
        self.token = token or settings.HOME_ASSISTANT_TOKEN
        self.timeout = timeout or settings.HOME_ASSISTANT_TIMEOUT_SECONDS
        self.opener = opener

    def sync(self):
        if not self.base_url or not self.token:
            raise HomeAssistantError("HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN must be configured.")

        registry = self._get_json(self.device_registry_path)
        states = self._get_json(self.states_path)
        state_attributes = self._state_attributes_by_device(states)
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

    @staticmethod
    def _state_attributes_by_device(states):
        attributes = {}
        for state in states:
            device_id = state.get("attributes", {}).get("device_id")
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