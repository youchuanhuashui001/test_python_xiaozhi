import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from client import WebSocketClient


class ClientIdentityTests(unittest.TestCase):
    def test_invalid_client_id_falls_back_to_persisted_uuid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "client_state.json"

            client = WebSocketClient(
                hostname="api.tenclass.net",
                port=443,
                path="/xiaozhi/v1/",
                device_id="d8:bb:c1:dc:02:d4",
                client_id="not-a-valid-uuid",
                state_file_path=state_path,
            )

            self.assertNotEqual(client.client_id, "not-a-valid-uuid")
            saved_state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(saved_state["client_id"], client.client_id)


class OtaBootstrapTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tempdir.name) / "client_state.json"

    async def asyncTearDown(self):
        self.tempdir.cleanup()

    async def test_apply_ota_ready_response_updates_websocket_target(self):
        client = WebSocketClient(
            hostname="api.tenclass.net",
            port=443,
            path="/xiaozhi/v1/",
            device_id="d8:bb:c1:dc:02:d4",
            client_id=None,
            state_file_path=self.state_path,
        )

        await client.bootstrap(ota_fetcher=lambda: {
            "websocket": {"url": "wss://example.com:9443/alt-path", "token": "ota-token"},
            "firmware": {"version": "1.6.0"},
        })

        self.assertEqual(client.uri, "wss://example.com:9443/alt-path")
        self.assertEqual(client.ws_token, "ota-token")

    async def test_activation_response_stops_before_websocket_connect(self):
        client = WebSocketClient(
            hostname="api.tenclass.net",
            port=443,
            path="/xiaozhi/v1/",
            device_id="d8:bb:c1:dc:02:d4",
            client_id=None,
            state_file_path=self.state_path,
        )

        websocket_connect = mock.MagicMock()
        with mock.patch("client.websockets.connect", websocket_connect):
            await client.connect(ota_fetcher=lambda: {
                "websocket": {"url": "wss://example.com/xiaozhi/v1/", "token": "ota-token"},
                "activation": {
                    "code": "123456",
                    "message": "xiaozhi.me\n123456",
                    "challenge": "challenge-token",
                },
            })

        websocket_connect.assert_not_called()
        self.assertEqual(client.activation_code, "123456")

    async def test_bootstrap_falls_back_when_asyncio_to_thread_is_unavailable(self):
        client = WebSocketClient(
            hostname="api.tenclass.net",
            port=443,
            path="/xiaozhi/v1/",
            device_id="d8:bb:c1:dc:02:d4",
            client_id=None,
            state_file_path=self.state_path,
        )

        with mock.patch("client.asyncio.to_thread", new=None, create=True):
            with mock.patch.object(client, "_fetch_ota_config", return_value={
                "websocket": {"url": "wss://example.com/xiaozhi/v1/", "token": "ota-token"},
            }) as fetch_mock:
                result = await client.bootstrap()

        self.assertTrue(result)
        fetch_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
