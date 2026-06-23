from __future__ import annotations

import hashlib
import ipaddress
import logging
import os
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
from mcp.server.fastmcp import FastMCP

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger("mineral-pdf-mcp")

mcp = FastMCP("mineral-pdf-mcp")

CACHE_DIR = Path(__file__).resolve().parents[1] / ".." / ".." / "data" / "cache"
CACHE_DIR = CACHE_DIR.resolve()
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MAX_PDF_SIZE = 50 * 1024 * 1024  # 50 MB
BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "[::1]"}


def _get_data_mode() -> str:
    explicit = os.environ.get("PDF_DATA_MODE", "").strip().lower()
    if explicit in {"live", "fixture"}:
        return explicit

    app_env = os.environ.get("APP_ENV", "development").strip().lower()
    return "fixture" if app_env == "development" else "live"


USE_FIXTURE = _get_data_mode() == "fixture"


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


def _validate_pdf_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported scheme: {parsed.scheme}")
    hostname = parsed.hostname or ""
    if hostname in BLOCKED_HOSTS:
        raise ValueError(f"Blocked host: {hostname}")
    if "metadata" in hostname:
        raise ValueError(f"Blocked metadata endpoint: {hostname}")
    _resolve_and_validate_host(hostname)


async def _download_pdf(url: str) -> Path:
    url_hash = hashlib.md5(url.encode()).hexdigest()
    cached = CACHE_DIR / f"{url_hash}.pdf"
    if cached.exists():
        logger.info("Using cached PDF: %s", cached)
        return cached

    _validate_pdf_url(url)

    async with httpx.AsyncClient(timeout=60, follow_redirects=True, max_redirects=5) as client:
        head_resp = await client.head(url)
        content_type = head_resp.headers.get("content-type", "")
        if "pdf" not in content_type and not url.lower().endswith(".pdf"):
            raise ValueError(f"URL does not appear to be a PDF: content-type={content_type}")

        content_length = int(head_resp.headers.get("content-length", 0))
        if content_length > MAX_PDF_SIZE:
            raise ValueError(f"PDF too large: {content_length} bytes (max {MAX_PDF_SIZE})")

        resp = await client.get(url)
        resp.raise_for_status()

        cached.write_bytes(resp.content)
        logger.info("Downloaded PDF to cache: %s (%d bytes)", cached, len(resp.content))
        return cached


@mcp.tool()
async def extract_resources(
    pdf_url: str,
    project_hint: str | None = None,
    categories: list[str] | None = None,
    commodities: list[str] | None = None,
    include_evidence: bool = True,
) -> dict:
    """Extract mineral resource data from a NI 43-101 or similar technical report PDF.

    Downloads the PDF, locates resource tables, and extracts structured data
    including category, tonnage, grade, and evidence text with page numbers.

    Args:
        pdf_url: URL of the PDF technical report
        project_hint: Optional project name to help identify deposit
        categories: Resource categories to extract (default: Indicated, Inferred)
        commodities: Filter to specific commodities
        include_evidence: Whether to include evidence text
    """
    logger.info("extract_resources called: url=%s hint=%s", pdf_url, project_hint)

    if categories is None:
        categories = ["Indicated", "Inferred"]

    if USE_FIXTURE:
        from app.providers.fixture import load_resource_fixture
        fixture = load_resource_fixture(pdf_url, project_hint=project_hint)
        if fixture:
            fixture["warnings"] = fixture.get("warnings", []) + ["Fixture data is being used."]
            return fixture

    if not pdf_url or not pdf_url.startswith(("http://", "https://")):
        return {
            "error_code": "INVALID_ARGUMENT",
            "message": f"Invalid PDF URL: '{pdf_url}'",
            "retryable": False,
            "component": "pdf",
        }

    try:
        pdf_path = await _download_pdf(pdf_url)
    except ValueError as exc:
        code = "PDF_TOO_LARGE" if "too large" in str(exc) else "PDF_DOWNLOAD_FAILED"
        return {
            "error_code": code,
            "message": str(exc),
            "retryable": "too large" not in str(exc),
            "component": "pdf",
        }
    except Exception as exc:
        logger.error("PDF download failed: %s", exc)
        return {
            "error_code": "PDF_DOWNLOAD_FAILED",
            "message": f"Failed to download PDF: {exc}",
            "retryable": True,
            "component": "pdf",
        }

    from app.providers.pdf_extractor import (
        extract_tables_from_page,
        find_resource_pages,
        parse_resource_table,
        parse_resource_text,
    )

    resource_pages = find_resource_pages(pdf_path)
    if not resource_pages:
        return {
            "error_code": "RESOURCE_TABLE_NOT_FOUND",
            "message": "No resource tables found in the PDF.",
            "retryable": False,
            "component": "pdf",
        }

    all_rows: list[dict] = []
    deposit_name = project_hint or "Unknown"

    for page_num in resource_pages[:10]:
        tables = extract_tables_from_page(pdf_path, page_num)
        for table in tables:
            rows = parse_resource_table(table, page_num, deposit_name)
            all_rows.extend(rows)

    if categories:
        cat_lower = {c.lower() for c in categories}
        all_rows = [r for r in all_rows if r["category"].lower() in cat_lower]

    if commodities:
        comm_lower = {c.lower() for c in commodities}
        all_rows = [r for r in all_rows if r["commodity"].lower() in comm_lower]

    if not include_evidence:
        for r in all_rows:
            r.pop("evidence_text", None)

    if not all_rows:
        try:
            import fitz
            doc = fitz.open(str(pdf_path))
            page_texts = []
            for pg in resource_pages[:5]:
                if pg < len(doc):
                    page_text = doc[pg].get_text()
                    page_texts.append({"page_number": pg + 1, "text": page_text})
                    all_rows.extend(parse_resource_text(page_text, pg, deposit_name))
            doc.close()

            if categories:
                cat_lower = {c.lower() for c in categories}
                all_rows = [r for r in all_rows if r["category"].lower() in cat_lower]

            if commodities:
                comm_lower = {c.lower() for c in commodities}
                all_rows = [r for r in all_rows if r["commodity"].lower() in comm_lower]

            if page_texts:
                from app.providers.llm_structurer import structure_with_llm
                if not all_rows:
                    llm_rows = await structure_with_llm(page_texts)
                    for lr in llm_rows:
                        lr.setdefault("deposit_name", deposit_name)
                        lr.setdefault("page_number", resource_pages[0] + 1)
                        lr.setdefault("confidence", 0.7)
                    all_rows = llm_rows
        except Exception as exc:
            logger.warning("LLM fallback extraction failed: %s", exc)

    return {
        "report": {
            "title": f"{deposit_name} Technical Report",
            "project_name": deposit_name,
            "effective_date": None,
            "pdf_url": pdf_url,
        },
        "resources": all_rows,
        "warnings": [] if all_rows else ["No resource rows could be extracted."],
        "status": "success" if all_rows else "partial",
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
