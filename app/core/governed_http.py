from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse, urlunparse

import requests
from requests.adapters import HTTPAdapter
from urllib3 import PoolManager

from app.core.egress_policy import EgressDenied


class _PinnedHTTPAdapter(HTTPAdapter):
    def __init__(self, hostname, address, *args, **kwargs):
        self._hostname = hostname
        self._address = str(address)
        super().__init__(*args, **kwargs)

    def get_connection_with_tls_context(self, request, verify, proxies=None, cert=None):
        proxy = None
        if proxies:
            proxy = proxies.get(request.url.split(":", 1)[0]) or proxies.get("all")
        if proxy:
            raise EgressDenied("pinned_egress_proxy_unsupported")
        host_params, pool_kwargs = self.build_connection_pool_key_attributes(request, verify, cert)
        pool_kwargs["assert_hostname"] = self._hostname
        pool_kwargs["server_hostname"] = self._hostname
        return self.poolmanager.connection_from_host(
            self._address, port=host_params.get("port"), scheme=host_params.get("scheme"), pool_kwargs=pool_kwargs
        )


def _resolve_public_addresses(hostname):
    try:
        literal = ipaddress.ip_address(hostname)
        addresses = [literal]
    except ValueError:
        try:
            infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
            addresses = [ipaddress.ip_address(info[4][0]) for info in infos]
        except OSError as exc:
            raise EgressDenied("dns_resolution_failed") from exc
    if not addresses or any(
        address.is_private or address.is_loopback or address.is_link_local
        or address.is_reserved or address.is_multicast for address in addresses
    ):
        raise EgressDenied("private_address_blocked")
    return addresses


def governed_request(method, url, *, allow_hosts=None, **kwargs):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise EgressDenied("invalid_egress_url")
    hostname = parsed.hostname.lower().rstrip(".")
    if allow_hosts is not None and hostname not in {host.lower().rstrip(".") for host in allow_hosts}:
        raise EgressDenied("destination_not_allowlisted")
    if kwargs.pop("allow_redirects", False):
        raise EgressDenied("redirects_not_allowed")
    kwargs["allow_redirects"] = False
    addresses = _resolve_public_addresses(hostname)
    pinned = addresses[0]
    session = requests.Session()
    adapter = _PinnedHTTPAdapter(hostname, pinned)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    headers = dict(kwargs.pop("headers", {}) or {})
    headers.setdefault("Host", hostname)
    target = urlunparse(parsed._replace(netloc=f"[{pinned}]" if pinned.version == 6 else str(pinned)))
    try:
        return session.request(method, target, headers=headers, **kwargs)
    finally:
        session.close()
