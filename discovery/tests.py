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


class FakeWebSocket:
    def __init__(self, messages):
        self.messages = iter(json.dumps(message) for message in messages)
        self.sent = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def recv(self):
        return next(self.messages)

    def send(self, message):
        self.sent.append(json.loads(message))


class FakeWebSocketFactory:
    def __init__(self, conversations):
        self.conversations = iter(conversations)
        self.sockets = []
        self.urls = []

    def __call__(self, url, timeout):
        self.urls.append(url)
        socket = FakeWebSocket(next(self.conversations))
        self.sockets.append(socket)
        return socket


def websocket_conversation(command, result):
    return [
        {"type": "auth_required"},
        {"type": "auth_ok"},
        {"id": 1, "type": "result", "success": True, "result": result},
    ]


@override_settings(HOME_ASSISTANT_URL="http://ha.test:8123", HOME_ASSISTANT_TOKEN="secret-token")
class HomeAssistantProviderTests(TestCase):
    def test_sync_imports_network_devices_and_skips_devices_without_ip(self):
        websocket_factory = FakeWebSocketFactory([
            websocket_conversation("config/device_registry/list", [
                {
                    "id": "device-1",
                    "name": "Living Room Sensor",
                    "connections": [["mac", "AA:BB:CC:DD:EE:FF"], ["ip", "192.168.88.20"]],
                    "manufacturer": "Example",
                    "model": "Sensor",
                },
                {"id": "device-2", "name": "Cloud Device", "connections": []},
            ]),
            websocket_conversation("config/entity_registry/list", [
                {"entity_id": "sensor.living_room", "device_id": "device-1"},
            ]),
        ])
        opener = Mock(side_effect=[
            FakeResponse([
                {"entity_id": "sensor.living_room", "attributes": {}},
            ]),
        ])

        summary = HomeAssistantProvider(opener=opener, websocket_factory=websocket_factory).sync()

        self.assertEqual(summary.discovered, 1)
        self.assertEqual(summary.skipped, 1)
        device = DiscoveredDevice.objects.get(external_id="device-1")
        self.assertEqual(device.ip_address, "192.168.88.20")
        self.assertEqual(device.source, DiscoveredDevice.Source.HOME_ASSISTANT)
        request = opener.call_args.args[0]
        self.assertEqual(request.headers["Authorization"], "Bearer secret-token")
        self.assertEqual(websocket_factory.urls, ["ws://ha.test:8123/api/websocket"] * 2)
        self.assertEqual(websocket_factory.sockets[0].sent[0], {"type": "auth", "access_token": "secret-token"})
        self.assertEqual(websocket_factory.sockets[0].sent[1], {"id": 1, "type": "config/device_registry/list"})

    def test_sync_is_idempotent_for_same_home_assistant_device(self):
        websocket_factory = FakeWebSocketFactory([
            websocket_conversation("config/device_registry/list", [{"id": "device-1", "name": "Old Name", "connections": [["ip", "192.168.88.20"]]}]),
            websocket_conversation("config/entity_registry/list", []),
            websocket_conversation("config/device_registry/list", [{"id": "device-1", "name": "New Name", "connections": [["ip", "192.168.88.20"]]}]),
            websocket_conversation("config/entity_registry/list", []),
        ])
        provider = HomeAssistantProvider(
            opener=Mock(side_effect=[FakeResponse([]), FakeResponse([])]),
            websocket_factory=websocket_factory,
        )

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
