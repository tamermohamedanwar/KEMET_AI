import ipaddress
import socket
from urllib.parse import urlparse


class EgressDenied(ValueError):
    pass


def validate_public_http_target(url: str, *, allow_hosts: set[str] | None = None, resolve_dns: bool = True) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise EgressDenied("invalid_egress_url")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise EgressDenied("private_hostname_blocked")
    if allow_hosts is not None and host not in allow_hosts:
        raise EgressDenied("destination_not_allowlisted")
    try:
        literal = ipaddress.ip_address(host)
        addresses = [literal]
    except ValueError:
        if not resolve_dns:
            return parsed.geturl()
        try:
            addresses = [ipaddress.ip_address(info[4][0]) for info in socket.getaddrinfo(host, None)]
        except OSError as exc:
            raise EgressDenied("dns_resolution_failed") from exc
    if not addresses or any(addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast for addr in addresses):
        raise EgressDenied("private_address_blocked")
    return parsed.geturl()
