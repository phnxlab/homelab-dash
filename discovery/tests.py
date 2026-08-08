import json
from unittest.mock import Mock

from django.test import TestCase, override_settings

from dashboard.models import DiscoveredDevice
from discovery.home_assistant import HomeAssistantError, HomeAssistantProvider


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.payload


@override_settings(HOME_ASSISTANT_URL="http://ha.test:8123", HOME_ASSISTANT_TOKEN="secret-token")
class HomeAssistantProviderTests(TestCase):
    def test_sync_imports_network_devices_and_skips_devices_without_ip(self):
        opener = Mock(side_effect=[
            FakeResponse([
                {
                    "id": "device-1",
                    "name": "Living Room Sensor",
                    "connections": [["mac", "AA:BB:CC:DD:EE:FF"], ["ip", "192.168.88.20"]],
                    "manufacturer": "Example",
                    "model": "Sensor",
                },
                {"id": "device-2", "name": "Cloud Device", "connections": []},
            ]),
            FakeResponse([
                {"entity_id": "sensor.living_room", "attributes": {"device_id": "device-1"}},
            ]),
        ])

        summary = HomeAssistantProvider(opener=opener).sync()

        self.assertEqual(summary.discovered, 1)
        self.assertEqual(summary.skipped, 1)
        device = DiscoveredDevice.objects.get(external_id="device-1")
        self.assertEqual(device.ip_address, "192.168.88.20")
        self.assertEqual(device.source, DiscoveredDevice.Source.HOME_ASSISTANT)
        request = opener.call_args_list[0].args[0]
        self.assertEqual(request.headers["Authorization"], "Bearer secret-token")

    def test_sync_is_idempotent_for_same_home_assistant_device(self):
        responses = [
            FakeResponse([{"id": "device-1", "name": "Old Name", "connections": [["ip", "192.168.88.20"]]}]),
            FakeResponse([]),
            FakeResponse([{"id": "device-1", "name": "New Name", "connections": [["ip", "192.168.88.20"]]}]),
            FakeResponse([]),
        ]
        provider = HomeAssistantProvider(opener=Mock(side_effect=responses))

        first = provider.sync()
        second = provider.sync()

        self.assertEqual(first.discovered, 1)
        self.assertEqual(second.updated, 1)
        self.assertEqual(DiscoveredDevice.objects.count(), 1)
        self.assertEqual(DiscoveredDevice.objects.get().hostname, "New Name")

    def test_missing_configuration_is_reported(self):
        with override_settings(HOME_ASSISTANT_URL="", HOME_ASSISTANT_TOKEN=""):
            with self.assertRaises(HomeAssistantError):
                HomeAssistantProvider().sync()
