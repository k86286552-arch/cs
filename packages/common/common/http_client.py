from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

import httpx

BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "[::1]"}
MAX_REDIRECTS = 5
DEFAULT_TIMEOUT = 30.0
MAX_RESPONSE_SIZE = 20 * 1024 * 1024  # 20 MB


def _is_private_ip(hostname: str) -> bool:
    try:
        ip = ipaddress.ip_address(hostname)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        return False


def validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported scheme: {parsed.scheme}")
    hostname = parsed.hostname or ""
    if hostname in BLOCKED_HOSTS or _is_private_ip(hostname):
        raise ValueError(f"Blocked host: {hostname}")
    if "metadata" in hostname or hostname.endswith(".internal"):
        raise ValueError(f"Blocked metadata endpoint: {hostname}")
    return url


def safe_client(**kwargs) -> httpx.AsyncClient:
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    kwargs.setdefault("max_redirects", MAX_REDIRECTS)
    kwargs.setdefault("follow_redirects", True)
    return httpx.AsyncClient(**kwargs)