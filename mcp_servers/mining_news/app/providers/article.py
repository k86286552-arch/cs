from __future__ import annotations

import hashlib
import ipaddress
import logging
import socket
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("mining-news-mcp")

HEADERS = {"User-Agent": "MineralDailyAgent/0.1 (research-bot)"}
MAX_RESPONSE_SIZE = 10 * 1024 * 1024  # 10 MB
BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "[::1]"}


def _is_blocked_ip(value: str) -> bool:
    ip = ipaddress.ip_address(value)
    return any(
        [
            ip.is_private,
            ip.is_loopback,
            ip.is_link_local,
            ip.is_multicast,
            ip.is_reserved,
            ip.is_unspecified,
        ]
    )


def _resolve_and_validate_host(hostname: str) -> None:
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        ip = None

    if ip is not None:
        if _is_blocked_ip(hostname):
            raise ValueError(f"Blocked IP address: {hostname}")
        return

    try:
        addrinfos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError(f"Failed to resolve host: {hostname}") from exc

    for family, _, _, _, sockaddr in addrinfos:
        address = sockaddr[0]
        if family in (socket.AF_INET, socket.AF_INET6) and _is_blocked_ip(address):
            raise ValueError(f"Blocked host: {hostname} resolved to {address}")


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported scheme: {parsed.scheme}")
    hostname = parsed.hostname or ""
    if hostname in BLOCKED_HOSTS:
        raise ValueError(f"Blocked host: {hostname}")
    if "metadata" in hostname:
        raise ValueError(f"Blocked metadata endpoint: {hostname}")
    _resolve_and_validate_host(hostname)


def _article_id(url: str) -> str:
    return "news_" + hashlib.md5(url.encode()).hexdigest()[:8]


async def fetch_article_content(url: str) -> dict:
    _validate_url(url)

    async with httpx.AsyncClient(timeout=20, headers=HEADERS, follow_redirects=True, max_redirects=5) as client:
        resp = await client.get(url)
        resp.raise_for_status()

        content_length = int(resp.headers.get("content-length", 0))
        if content_length > MAX_RESPONSE_SIZE:
            raise ValueError(f"Response too large: {content_length} bytes")

        html = resp.text

    parser_used = "trafilatura"
    title = ""
    content = ""
    pub_date = None
    confidence = 0.0

    try:
        import trafilatura
        result = trafilatura.extract(html, include_comments=False, include_tables=True, output_format="txt")
        metadata = trafilatura.extract(html, output_format="xmltei")

        if result:
            content = result
            confidence = 0.9

        doc = trafilatura.bare_extraction(html)
        if doc:
            title = doc.get("title", "") or ""
            pub_date = doc.get("date", None)
    except Exception:
        parser_used = "bs4"
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else ""
            article_tag = soup.find("article") or soup.find("div", class_="article-body") or soup.body
            if article_tag:
                for tag in article_tag.find_all(["script", "style", "nav", "header", "footer"]):
                    tag.decompose()
                content = article_tag.get_text(separator="\n", strip=True)
                confidence = 0.7
        except Exception:
            content = ""
            confidence = 0.0

    source_name = urlparse(url).netloc.replace("www.", "").upper().split(".")[0]

    return {
        "article_id": _article_id(url),
        "title": title,
        "published_at": str(pub_date) if pub_date else None,
        "source_name": source_name,
        "source_url": url,
        "content": content[:10000],
        "summary": None,
        "parser": parser_used,
        "confidence": confidence,
        "warnings": [] if content else ["Failed to extract article content."],
    }
