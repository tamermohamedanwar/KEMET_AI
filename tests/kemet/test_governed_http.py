import ipaddress

from app.core.egress_policy import EgressDenied
from app.core.governed_http import _PinnedHTTPAdapter, _resolve_public_addresses, governed_request


def test_dns_binding_resolves_all_addresses_and_rejects_private(monkeypatch):
    public = ("AF_INET", None, None, None, ("93.184.216.34", 443))
    private = ("AF_INET", None, None, None, ("10.0.0.1", 443))
    monkeypatch.setattr("app.core.governed_http.socket.getaddrinfo", lambda *a, **k: [public, private])
    try:
        _resolve_public_addresses("example.com")
        assert False, "private address must be rejected"
    except EgressDenied as exc:
        assert str(exc) == "private_address_blocked"


def test_pinned_adapter_binds_ip_but_preserves_tls_hostname(monkeypatch):
    adapter = _PinnedHTTPAdapter("api.example.com", ipaddress.ip_address("93.184.216.34"))
    captured = {}

    class Pool:
        def connection_from_host(self, host, port=None, scheme=None, pool_kwargs=None):
            captured.update(host=host, port=port, scheme=scheme, pool_kwargs=pool_kwargs)
            return object()

    adapter.poolmanager = Pool()
    request = type("Request", (), {"url": "https://api.example.com/v1/test"})()
    monkeypatch.setattr(adapter, "build_connection_pool_key_attributes", lambda request, verify, cert: (
        {"host": "api.example.com", "port": 443, "scheme": "https"}, {}
    ))
    adapter.get_connection_with_tls_context(request, True)
    assert captured["host"] == "93.184.216.34"
    assert captured["pool_kwargs"]["assert_hostname"] == "api.example.com"
    assert captured["pool_kwargs"]["server_hostname"] == "api.example.com"


def test_governed_request_resists_dns_rebinding_between_validation_and_connection(monkeypatch):
    public = ("AF_INET", None, None, None, ("93.184.216.34", 443))
    private = ("AF_INET", None, None, None, ("10.0.0.1", 443))
    calls = []

    def resolve(*args, **kwargs):
        calls.append(1)
        return [public] if len(calls) == 1 else [private]

    monkeypatch.setattr("app.core.governed_http.socket.getaddrinfo", resolve)
    captured = {}

    class Session:
        def mount(self, *args):
            return None

        def request(self, method, url, **kwargs):
            captured.update(method=method, url=url, kwargs=kwargs)
            return object()

        def close(self):
            return None

    monkeypatch.setattr("app.core.governed_http.requests.Session", Session)
    governed_request("GET", "https://api.example.com/v1", allow_hosts={"api.example.com"})
    assert calls == [1]
    assert captured["url"] == "https://93.184.216.34/v1"


def test_governed_request_uses_pinned_ip_and_host_header(monkeypatch):
    public = ("AF_INET", None, None, None, ("93.184.216.34", 443))
    monkeypatch.setattr("app.core.governed_http.socket.getaddrinfo", lambda *a, **k: [public])
    captured = {}

    class Session:
        def mount(self, *args):
            return None

        def request(self, method, url, **kwargs):
            captured.update(method=method, url=url, kwargs=kwargs)
            return object()

        def close(self):
            return None

    monkeypatch.setattr("app.core.governed_http.requests.Session", Session)
    governed_request("GET", "https://api.example.com/v1", allow_hosts={"api.example.com"})
    assert captured["url"] == "https://93.184.216.34/v1"
    assert captured["kwargs"]["headers"]["Host"] == "api.example.com"

def test_governed_request_rejects_redirect_following(monkeypatch):
    public = ("AF_INET", None, None, None, ("93.184.216.34", 443))
    monkeypatch.setattr("app.core.governed_http.socket.getaddrinfo", lambda *a, **k: [public])
    try:
        governed_request("GET", "https://api.example.com/v1", allow_hosts={"api.example.com"}, allow_redirects=True)
        assert False, "redirect following must be rejected"
    except EgressDenied as exc:
        assert str(exc) == "redirects_not_allowed"


def test_governed_request_forces_redirects_off(monkeypatch):
    public = ("AF_INET", None, None, None, ("93.184.216.34", 443))
    monkeypatch.setattr("app.core.governed_http.socket.getaddrinfo", lambda *a, **k: [public])
    captured = {}

    class Session:
        def mount(self, *args):
            return None

        def request(self, method, url, **kwargs):
            captured.update(kwargs=kwargs)
            return object()

        def close(self):
            return None

    monkeypatch.setattr("app.core.governed_http.requests.Session", Session)
    governed_request("GET", "https://api.example.com/v1", allow_hosts={"api.example.com"})
    assert captured["kwargs"]["allow_redirects"] is False

