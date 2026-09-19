from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit


class SSRFSecurityError(ValueError):
    """Raised when a URL violates SSRF safety rules or allow-lists."""
    pass


DEFAULT_ALLOWED_DOMAINS: tuple[str, ...] = (
    "incois.gov.in",
    "weather.gov",
    "copernicus.eu",
    "nasa.gov",
    "openstreetmap.org",
)

ALLOWED_SCHEMES: tuple[str, ...] = ("http", "https")

BLOCKED_IP_NETWORKS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.88.99.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


def is_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address falls within private, loopback, link-local, or reserved space."""
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return True
    for network in BLOCKED_IP_NETWORKS:
        if ip in network:
            return True
    return False


def is_domain_allowed(hostname: str, allowed_domains: tuple[str, ...]) -> bool:
    """Check if hostname matches or is a subdomain of an allowed domain."""
    hostname_clean = hostname.lower().strip(".")
    for domain in allowed_domains:
        domain_clean = domain.lower().strip(".")
        if hostname_clean == domain_clean or hostname_clean.endswith(f".{domain_clean}"):
            return True
    return False


def validate_url(
    url: str,
    *,
    allowed_domains: tuple[str, ...] | None = None,
    check_dns: bool = True,
) -> str:
    """Validate a URL against SSRF policy: scheme, allow-listed domain, and non-private IP.
    
    Raises:
        SSRFSecurityError: If URL scheme is unsafe, domain is not allowed, or resolves to a private IP.
    """
    if not url or not isinstance(url, str):
        raise SSRFSecurityError("URL must be a non-empty string.")

    try:
        parsed = urlsplit(url.strip())
    except Exception as exc:
        raise SSRFSecurityError(f"Malformed URL: {url}") from exc

    if not parsed.scheme or parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise SSRFSecurityError(
            f"Scheme '{parsed.scheme}' is blocked. Only {ALLOWED_SCHEMES} are allowed."
        )

    hostname = parsed.hostname
    if not hostname:
        raise SSRFSecurityError("URL does not contain a valid hostname.")

    allowed = allowed_domains if allowed_domains is not None else DEFAULT_ALLOWED_DOMAINS

    # Check if host is direct raw IP
    try:
        ip = ipaddress.ip_address(hostname)
        if is_ip_blocked(ip):
            raise SSRFSecurityError(f"Direct IP target {hostname} is blocked (private/reserved address).")
        # Direct public IP is only allowed if explicitly in allowed domains
        if not is_domain_allowed(hostname, allowed):
            raise SSRFSecurityError(f"Direct IP {hostname} is not in the allowed domain list.")
        return url
    except ValueError:
        # Not a raw IP literal, treat as hostname
        pass

    # Check domain against allow-list
    if not is_domain_allowed(hostname, allowed):
        raise SSRFSecurityError(
            f"Domain '{hostname}' is not authorized. Allowed domains: {allowed}"
        )

    # DNS resolution check to prevent DNS rebinding attacks
    if check_dns:
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for item in addr_info:
                sockaddr = item[4]
                ip_str = sockaddr[0]
                ip = ipaddress.ip_address(ip_str)
                if is_ip_blocked(ip):
                    raise SSRFSecurityError(
                        f"Domain '{hostname}' resolved to blocked IP {ip_str}."
                    )
        except socket.gaierror as exc:
            # If domain cannot be resolved at validation time (e.g. offline mock test or DNS failure)
            # In offline environments, let caller decide or raise
            raise SSRFSecurityError(f"DNS resolution failed for '{hostname}': {exc}") from exc

    return url
