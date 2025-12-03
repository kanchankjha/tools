import json
import urllib.error
import urllib.request
from typing import Any, Dict
from unittest.mock import MagicMock, Mock, patch

import pytest

from meraki_snapshot.client import MerakiClient, MerakiHttpError


class TestMerakiHttpError:
    def test_error_attributes(self):
        error = MerakiHttpError(404, "Not found", body='{"error": "Network not found"}')
        assert error.status == 404
        assert str(error) == "Not found"
        assert error.body == '{"error": "Network not found"}'


class TestMerakiClient:
    def test_client_initialization(self):
        client = MerakiClient(
            api_key="test_key",
            org_id="123456",
            base_url="https://api.meraki.com/api/v1",
            timeout=30,
            max_retries=5,
        )
        assert client.api_key == "test_key"
        assert client.org_id == "123456"
        assert client.base_url == "https://api.meraki.com/api/v1"
        assert client.timeout == 30
        assert client.max_retries == 5

    @patch("urllib.request.urlopen")
    def test_get_organization(self, mock_urlopen):
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({"id": "123", "name": "Test Org"}).encode("utf-8")
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = MerakiClient(api_key="test", org_id="123")
        result = client.get_organization()

        assert result["id"] == "123"
        assert result["name"] == "Test Org"

    @patch("urllib.request.urlopen")
    def test_list_networks(self, mock_urlopen):
        networks = [{"id": "N_1", "name": "Network 1"}, {"id": "N_2", "name": "Network 2"}]
        mock_response = Mock()
        mock_response.read.return_value = json.dumps(networks).encode("utf-8")
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = MerakiClient(api_key="test", org_id="123")
        result = client.list_networks()

        assert len(result) == 2
        assert result[0]["id"] == "N_1"

    @patch("urllib.request.urlopen")
    def test_list_devices(self, mock_urlopen):
        devices = [{"serial": "Q2XX-1234", "model": "MX68"}]
        mock_response = Mock()
        mock_response.read.return_value = json.dumps(devices).encode("utf-8")
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = MerakiClient(api_key="test", org_id="123")
        result = client.list_devices("N_1")

        assert len(result) == 1
        assert result[0]["serial"] == "Q2XX-1234"

    @patch("urllib.request.urlopen")
    def test_list_org_admins(self, mock_urlopen):
        admins = [{"id": "A1", "email": "admin@example.com"}]
        mock_response = Mock()
        mock_response.read.return_value = json.dumps(admins).encode("utf-8")
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = MerakiClient(api_key="test", org_id="123")
        result = client.list_org_admins()

        assert len(result) == 1
        assert result[0]["email"] == "admin@example.com"

    @patch("urllib.request.urlopen")
    def test_list_config_templates(self, mock_urlopen):
        templates = [{"id": "T1", "name": "Default Template"}]
        mock_response = Mock()
        mock_response.read.return_value = json.dumps(templates).encode("utf-8")
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = MerakiClient(api_key="test", org_id="123")
        result = client.list_config_templates()

        assert len(result) == 1
        assert result[0]["name"] == "Default Template"

    @patch("urllib.request.urlopen")
    def test_fetch_appliance_config(self, mock_urlopen):
        config = {"vlans": [{"id": 1, "name": "Default"}]}
        mock_response = Mock()
        mock_response.read.return_value = json.dumps(config).encode("utf-8")
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = MerakiClient(api_key="test", org_id="123")
        result = client.fetch_appliance_config("N_1")

        assert "settings" in result
        assert "vlans" in result

    @patch("urllib.request.urlopen")
    def test_fetch_switch_config(self, mock_urlopen):
        config = {"stp": {"enabled": True}}
        mock_response = Mock()
        mock_response.read.return_value = json.dumps(config).encode("utf-8")
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = MerakiClient(api_key="test", org_id="123")
        result = client.fetch_switch_config("N_1")

        assert "stp" in result
        assert "dhcp_server_policy" in result

    @patch("urllib.request.urlopen")
    def test_fetch_wireless_config(self, mock_urlopen):
        config = {"ssids": [{"number": 0, "name": "Corp"}]}
        mock_response = Mock()
        mock_response.read.return_value = json.dumps(config).encode("utf-8")
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = MerakiClient(api_key="test", org_id="123")
        result = client.fetch_wireless_config("N_1")

        assert "ssids" in result
        assert "rf_profiles" in result

    @patch("urllib.request.urlopen")
    def test_fetch_camera_config(self, mock_urlopen):
        config = {"video_settings": {"enabled": True}}
        mock_response = Mock()
        mock_response.read.return_value = json.dumps(config).encode("utf-8")
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = MerakiClient(api_key="test", org_id="123")
        result = client.fetch_camera_config("N_1")

        assert "video_settings" in result

    @patch("urllib.request.urlopen")
    def test_collect_network_config_all_products(self, mock_urlopen):
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({"test": "data"}).encode("utf-8")
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = MerakiClient(api_key="test", org_id="123")
        result = client.collect_network_config("N_1", ["appliance", "switch", "wireless", "camera"])

        assert "appliance" in result
        assert "switch" in result
        assert "wireless" in result
        assert "camera" in result

    def test_apply_network_config_appliance(self):
        client = MerakiClient(api_key="test", org_id="123")
        config = {"appliance": {"vlans": [{"id": 1}]}}
        operations = client.apply_network_config("N_1", config)

        assert "appliance.vlans planned" in operations

    def test_apply_network_config_switch(self):
        client = MerakiClient(api_key="test", org_id="123")
        config = {"switch": {"switch_ports": [{"portId": 1}]}}
        operations = client.apply_network_config("N_1", config)

        assert "switch.ports planned" in operations

    def test_apply_network_config_wireless(self):
        client = MerakiClient(api_key="test", org_id="123")
        config = {"wireless": {"ssids": [{"number": 0}]}}
        operations = client.apply_network_config("N_1", config)

        assert "wireless.ssids planned" in operations

    def test_apply_network_config_camera(self):
        client = MerakiClient(api_key="test", org_id="123")
        config = {"camera": {"video_settings": {"enabled": True}}}
        operations = client.apply_network_config("N_1", config)

        assert "camera.video planned" in operations

    def test_apply_network_config_empty(self):
        client = MerakiClient(api_key="test", org_id="123")
        operations = client.apply_network_config("N_1", {})

        assert operations == []

    @patch("urllib.request.urlopen")
    def test_http_error_404_allowed(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://test.com",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None,
        )

        client = MerakiClient(api_key="test", org_id="123")
        result = client._get("/test/path", allow_404=True)

        assert result is None

    @patch("urllib.request.urlopen")
    @patch("time.sleep")
    def test_http_error_429_retry(self, mock_sleep, mock_urlopen):
        # First call returns 429, second succeeds
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({"success": True}).encode("utf-8")
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        error = urllib.error.HTTPError(
            url="http://test.com",
            code=429,
            msg="Rate Limited",
            hdrs={"Retry-After": "1"},
            fp=None,
        )

        mock_urlopen.side_effect = [error, mock_response]

        client = MerakiClient(api_key="test", org_id="123", max_retries=3)
        result = client._get("/test/path")

        assert result["success"] is True
        mock_sleep.assert_called_once_with(1.0)

    @patch("urllib.request.urlopen")
    @patch("time.sleep")
    def test_http_error_500_retry(self, mock_sleep, mock_urlopen):
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({"recovered": True}).encode("utf-8")
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        error = urllib.error.HTTPError(
            url="http://test.com",
            code=500,
            msg="Server Error",
            hdrs={},
            fp=None,
        )

        mock_urlopen.side_effect = [error, mock_response]

        client = MerakiClient(api_key="test", org_id="123", max_retries=3)
        result = client._get("/test/path")

        assert result["recovered"] is True

    @patch("urllib.request.urlopen")
    def test_http_error_400_no_retry(self, mock_urlopen):
        error = urllib.error.HTTPError(
            url="http://test.com",
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=Mock(read=lambda: b'{"error": "bad"}'),
        )

        mock_urlopen.side_effect = error

        client = MerakiClient(api_key="test", org_id="123")

        with pytest.raises(MerakiHttpError) as exc_info:
            client._get("/test/path")

        assert exc_info.value.status == 400

    @patch("urllib.request.urlopen")
    @patch("time.sleep")
    def test_url_error_retry_exhausted(self, mock_sleep, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Network unreachable")

        client = MerakiClient(api_key="test", org_id="123", max_retries=2)

        with pytest.raises(MerakiHttpError) as exc_info:
            client._get("/test/path")

        assert exc_info.value.status == -1
        assert mock_sleep.call_count == 2

    @patch("urllib.request.urlopen")
    def test_empty_response(self, mock_urlopen):
        mock_response = Mock()
        mock_response.read.return_value = b""
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = MerakiClient(api_key="test", org_id="123")
        result = client._get("/test/path")

        assert result is None

    @patch("urllib.request.urlopen")
    def test_put_request(self, mock_urlopen):
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({"updated": True}).encode("utf-8")
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = MerakiClient(api_key="test", org_id="123")
        result = client._put("/test/path", {"field": "value"})

        assert result["updated"] is True

    @patch("urllib.request.urlopen")
    def test_post_request(self, mock_urlopen):
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({"created": True}).encode("utf-8")
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = MerakiClient(api_key="test", org_id="123")
        result = client._post("/test/path", {"field": "value"})

        assert result["created"] is True
