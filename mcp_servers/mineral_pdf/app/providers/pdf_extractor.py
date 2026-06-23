from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

logger = logging.getLogger("mineral-pdf-mcp")

RESOURCE_KEYWORDS = [
    "mineral resource", "resource estimate", "resource statement",
    "indicated", "inferred", "measured",
    "ore tonnage", "grade", "contained metal",
]

CATEGORY_PATTERNS = re.compile(
    r"\b(Measured|Indicated|Inferred|Probable|Proven|Measured\s*\+\s*Indicated)\b",
    re.IGNORECASE,
)

TEXT_CATEGORY_NAMES = {
    "measured",
    "indicated",
    "inferred",
    "probable",
    "proved",
    "proven",
    "measured+indicated",
    "measured + indicated",
}


def find_resource_pages(pdf_path: str | Path) -> list[int]:
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(pdf_path))
        pages = []
        for page_num in range(len(doc)):
            text = doc[page_num].get_text().lower()
            score = sum(1 for kw in RESOURCE_KEYWORDS if kw in text)
            if score >= 2:
                pages.append(page_num)
        doc.close()
        return pages
    except Exception as exc:
        logger.error("PyMuPDF page scan failed: %s", exc)
        return []


def extract_tables_from_page(pdf_path: str | Path, page_num: int) -> list[list[list[str]]]:
    tables: list[list[list[str]]] = []
    try:
        import pdfplumber
        pdf = pdfplumber.open(str(pdf_path))
        if page_num < len(pdf.pages):
            page = pdf.pages[page_num]
            page_tables = page.extract_tables()
            if page_tables:
                tables.extend(page_tables)
        pdf.close()
    except Exception as exc:
        logger.warning("pdfplumber extraction failed on page %d: %s", page_num, exc)
    return tables


def parse_resource_table(table: list[list[str]], page_num: int, deposit_hint: str = "") -> list[dict]:
    rows: list[dict] = []
    if not table or len(table) < 2:
        return rows

    header = [str(cell).lower().strip() if cell else "" for cell in table[0]]

    col_map: dict[str, int] = {}
    for i, h in enumerate(header):
        if "category" in h or "class" in h:
            col_map["category"] = i
        elif "tonnage" in h or "tonnes" in h or "mt" in h or "ore" in h:
            col_map["tonnage"] = i
        elif "grade" in h or "li2o" in h or "cu" in h or "fe" in h:
            col_map["grade"] = i
        elif "contained" in h or "metal" in h:
            col_map["contained"] = i

    for data_row in table[1:]:
        if not data_row or all(not cell for cell in data_row):
            continue

        cells = [str(cell).strip() if cell else "" for cell in data_row]
        row_text = " ".join(cells)
        cat_match = CATEGORY_PATTERNS.search(row_text)
        if not cat_match:
            continue

        category = cat_match.group(1).title()

        tonnage = _extract_number(cells, col_map.get("tonnage"))
        grade = _extract_number(cells, col_map.get("grade"))
        contained = _extract_number(cells, col_map.get("contained"))

        grade_unit = _detect_grade_unit(row_text)

        rows.append({
            "deposit_name": deposit_hint or "Unknown",
            "category": category,
            "commodity": _detect_commodity(grade_unit),
            "ore_tonnage": tonnage,
            "ore_tonnage_unit": "Mt",
            "grade": grade,
            "grade_unit": grade_unit,
            "contained_metal": contained,
            "contained_metal_unit": None,
            "page_number": page_num + 1,
            "table_title": "Mineral Resource Estimate",
            "evidence_text": row_text[:200],
            "confidence": 0.85 if tonnage and grade else 0.5,
        })

    return rows


def parse_resource_text(page_text: str, page_num: int, deposit_hint: str = "") -> list[dict]:
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    if not lines:
        return []

    rows: list[dict] = []
    current_table_title = "Mineral Resource Estimate"
    current_commodity = "lithium" if "li2o" in page_text.lower() else "unknown"
    current_grade_unit = "% Li2O" if "li2o" in page_text.lower() else "%"
    capture_table = not deposit_hint
    current_scope: str | None = None

    i = 0
    while i < len(lines):
        lower = lines[i].lower()
        if lower.startswith("table 5:") and "mineral resource" in lower:
            current_table_title = "Mineral Resource Estimate"
            capture_table = _matches_project_context(lower, deposit_hint)
            current_scope = None
        elif lower.startswith("table 6:") and "ore reserve" in lower:
            current_table_title = "Ore Reserve Estimate"
            capture_table = _matches_project_context(lower, deposit_hint)
            current_scope = None
        elif lower.startswith("table "):
            capture_table = _matches_project_context(lower, deposit_hint)
            current_scope = None

        if "in-situ" in lower or "in‑situ" in lower:
            current_scope = "in_situ"
        elif "stockpiles" in lower:
            current_scope = "stockpiles"
        elif deposit_hint and _matches_project_context(lower, deposit_hint):
            current_scope = "total"

        category = _normalize_text_category(lines[i])
        if category and capture_table and current_scope == "in_situ":
            numeric_values: list[float] = []
            raw_values: list[str] = []
            j = i + 1
            while j < len(lines) and len(numeric_values) < 4:
                candidate = lines[j]
                if _normalize_text_category(candidate):
                    break
                if candidate.lower().startswith("table "):
                    break
                parsed = _parse_float(candidate)
                if parsed is not None:
                    numeric_values.append(parsed)
                    raw_values.append(candidate)
                j += 1

            if len(numeric_values) >= 2:
                rows.append({
                    "deposit_name": deposit_hint or "Unknown",
                    "category": category,
                    "commodity": current_commodity,
                    "ore_tonnage": numeric_values[0],
                    "ore_tonnage_unit": "Mt",
                    "grade": numeric_values[1],
                    "grade_unit": current_grade_unit,
                    "contained_metal": None,
                    "contained_metal_unit": None,
                    "page_number": page_num + 1,
                    "table_title": current_table_title,
                    "evidence_text": " ".join([lines[i], *raw_values[:4]])[:200],
                    "confidence": 0.8,
                })
                i = j
                continue
        i += 1

    return rows


def _extract_number(cells: list[str], col_idx: int | None) -> float | None:
    if col_idx is not None and col_idx < len(cells):
        return _parse_float(cells[col_idx])
    for cell in cells:
        val = _parse_float(cell)
        if val is not None and val > 0:
            return val
    return None


def _parse_float(s: str) -> float | None:
    s = s.replace(",", "").replace(" ", "").strip()
    match = re.search(r"[\d.]+", s)
    if match:
        try:
            return float(match.group())
        except ValueError:
            pass
    return None


def _detect_grade_unit(text: str) -> str:
    text_lower = text.lower()
    if "li2o" in text_lower:
        return "% Li2O"
    if "% cu" in text_lower or "cu %" in text_lower:
        return "% Cu"
    if "% fe" in text_lower or "fe %" in text_lower:
        return "% Fe"
    if "g/t" in text_lower or "ppm" in text_lower:
        return "g/t"
    return "%"


def _detect_commodity(grade_unit: str) -> str:
    mapping = {
        "Li2O": "lithium",
        "Cu": "copper",
        "Fe": "iron_ore",
        "Au": "gold",
    }
    for key, commodity in mapping.items():
        if key in grade_unit:
            return commodity
    return "unknown"


def _normalize_text_category(value: str) -> str | None:
    compact = value.strip().lower().replace("‑", "-")
    compact = compact.replace("-", " ")
    compact = re.sub(r"\s+", " ", compact)
    if compact not in TEXT_CATEGORY_NAMES:
        return None
    if compact == "proven":
        return "Proved"
    if compact == "measured indicated" or compact == "measured + indicated":
        return "Measured+Indicated"
    return compact.title()


def _matches_project_context(value: str, deposit_hint: str) -> bool:
    if not deposit_hint:
        return True

    haystack = value.lower()
    tokens = [
        token.lower()
        for token in re.split(r"[^a-zA-Z0-9]+", deposit_hint)
        if token and len(token) >= 4
    ]
    if not tokens:
        return False
    return any(token in haystack for token in tokens)
