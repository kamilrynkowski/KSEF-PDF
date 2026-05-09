from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_DATE_RE = re.compile(r"(?<!\d)(\d{4}[-./]\d{2}[-./]\d{2}|\d{2}[-./]\d{2}[-./]\d{4})(?!\d)")
_INVOICE_PATTERNS = [
    re.compile(r"(?:numer\s+(?:faktury|dokumentu)|nr\s+(?:faktury|fa|fv)|faktura\s+(?:vat\s+)?(?:nr|numer))\s*[:#-]?\s*([^\n\r]+)", re.I),
    re.compile(r"\b(?:FV|FA|Faktura)\s*[/\\-]?[A-Z0-9][A-Z0-9/\\._ -]{2,40}", re.I),
]
_SELLER_LABELS = (
    "sprzedawca",
    "dostawca",
    "podmiot1",
    "wystawca",
)
_BUYER_LABELS = (
    "nabywca",
    "odbiorca",
    "podmiot2",
    "kupujący",
    "platnik",
    "płatnik",
)
_PRODUCT_HEADERS = (
    "nazwa towaru lub usługi",
    "nazwa towaru/usługi",
    "nazwa towaru",
    "nazwa usługi",
    "towar/usługa",
    "opis",
)
_STOP_WORDS = (
    "razem",
    "suma",
    "wartość netto",
    "wartosc netto",
    "stawka vat",
    "kwota vat",
    "wartość brutto",
    "wartosc brutto",
    "lp.",
)


@dataclass(frozen=True)
class InvoiceData:
    issue_date: str
    invoice_number: str
    seller: str
    item_name: str


def extract_text_from_pdf(path: str | Path) -> str:
    """Extract selectable text from a PDF file."""
    import fitz

    text_parts: list[str] = []
    with fitz.open(path) as document:
        for page in document:
            text_parts.append(page.get_text("text"))
    return "\n".join(text_parts)


def extract_invoice_data(path: str | Path) -> InvoiceData:
    """Read a KSeF/invoice PDF and infer fields required for a target filename."""
    text = _normalise_text(extract_text_from_pdf(path))
    if not text.strip():
        raise ValueError("Nie udało się odczytać tekstu z PDF. Plik może wymagać OCR.")

    return InvoiceData(
        issue_date=_extract_issue_date(text),
        invoice_number=_extract_invoice_number(text),
        seller=_extract_seller(text),
        item_name=_extract_item_name(text),
    )


def make_target_filename(data: InvoiceData, extension: str = ".pdf") -> str:
    parts = [data.issue_date, data.invoice_number, data.seller, data.item_name]
    safe_parts = [sanitize_filename_part(part) or "brak" for part in parts]
    return "_".join(safe_parts) + extension.lower()


def ensure_unique_filename(filename: str, existing: Iterable[str]) -> str:
    existing_set = set(existing)
    if filename not in existing_set:
        return filename

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    index = 2
    while True:
        candidate = f"{stem}_{index}{suffix}"
        if candidate not in existing_set:
            return candidate
        index += 1


def sanitize_filename_part(value: str, max_length: int = 80) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" ._-\t\n\r")
    value = value.replace("/", "-")
    if len(value) > max_length:
        value = value[:max_length].rstrip(" ._-")
    return value


def _normalise_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _extract_issue_date(text: str) -> str:
    patterns = [
        r"data\s+wystawienia\s*[:#-]?\s*([^\n\r]+)",
        r"data\s+sporządzenia\s*[:#-]?\s*([^\n\r]+)",
        r"p_1\s*[:#-]?\s*([^\n\r]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            date_match = _DATE_RE.search(match.group(1))
            if date_match:
                return _format_date(date_match.group(1))

    first_date = _DATE_RE.search(text)
    if first_date:
        return _format_date(first_date.group(1))
    raise ValueError("Nie znaleziono daty wystawienia.")


def _format_date(value: str) -> str:
    value = value.replace("/", "-").replace(".", "-")
    if re.match(r"\d{2}-\d{2}-\d{4}$", value):
        day, month, year = value.split("-")
        return f"{year}-{month}-{day}"
    return value


def _extract_invoice_number(text: str) -> str:
    for pattern in _INVOICE_PATTERNS:
        match = pattern.search(text)
        if match:
            value = match.group(1) if match.lastindex else match.group(0)
            value = _clean_value(value)
            if value:
                return value
    raise ValueError("Nie znaleziono numeru faktury.")


def _extract_seller(text: str) -> str:
    lines = _lines(text)
    for index, line in enumerate(lines):
        lower = line.lower().rstrip(":")
        if any(label in lower for label in _SELLER_LABELS):
            inline = _value_after_label(line, _SELLER_LABELS)
            candidate = inline or _first_meaningful_line(lines[index + 1 : index + 8])
            if candidate:
                return _clean_company_name(candidate)

    tax_id_match = re.search(r"(?:nip\s+sprzedawcy|sprzedawca[\s\S]{0,160}?nip)\s*[:#-]?\s*\d", text, re.I)
    if tax_id_match:
        before = text[: tax_id_match.start()].splitlines()[-5:]
        candidate = _first_meaningful_line(reversed(before))
        if candidate:
            return _clean_company_name(candidate)

    raise ValueError("Nie znaleziono nazwy sprzedawcy.")


def _extract_item_name(text: str) -> str:
    lines = _lines(text)
    for index, line in enumerate(lines):
        lower = line.lower()
        if any(header in lower for header in _PRODUCT_HEADERS):
            inline = _value_after_label(line, _PRODUCT_HEADERS)
            if inline and not inline.startswith("/") and not _looks_like_table_header(inline):
                return _clean_value(inline)
            candidate = _first_product_line(lines[index + 1 : index + 12])
            if candidate:
                return candidate

    lp_match = re.search(r"\blp\.?\s+.*?(?:nazwa|opis).*?\n([\s\S]{1,300})", text, re.I)
    if lp_match:
        candidate = _first_product_line(lp_match.group(1).splitlines())
        if candidate:
            return candidate

    raise ValueError("Nie znaleziono nazwy towaru/usługi.")


def _lines(text: str) -> list[str]:
    return [_clean_value(line) for line in text.splitlines() if _clean_value(line)]


def _clean_value(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" :;,-\t\n\r")
    value = re.sub(r"\b(NIP|REGON|KRS)\b.*$", "", value, flags=re.I).strip(" :;,-")
    return value


def _clean_company_name(value: str) -> str:
    value = _clean_value(value)
    value = re.sub(r"^(?:nazwa|firma)\s*[:#-]?\s*", "", value, flags=re.I).strip()
    return value


def _value_after_label(line: str, labels: Iterable[str]) -> str:
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*[:#-]?\s*(.+)$", line, re.I)
        if match:
            return _clean_value(match.group(1))
    return ""


def _first_meaningful_line(lines: Iterable[str]) -> str:
    for line in lines:
        cleaned = _clean_value(line)
        lower = cleaned.lower()
        if not cleaned:
            continue
        if any(label in lower for label in _BUYER_LABELS + _SELLER_LABELS):
            continue
        if lower.startswith(("nip", "regon", "krs", "adres", "ul.", "konto", "bank")):
            continue
        return cleaned
    return ""


def _first_product_line(lines: Iterable[str]) -> str:
    for line in lines:
        cleaned = _clean_value(line)
        lower = cleaned.lower()
        if not cleaned or _looks_like_table_header(cleaned):
            continue
        if any(stop in lower for stop in _STOP_WORDS):
            continue
        cleaned = re.sub(r"^\d+\.?\s+", "", cleaned)
        cleaned = re.sub(r"\s+\d+(?:[,.]\d+)?\s*(?:szt|usł|usl|kg|m|kpl)?\b.*$", "", cleaned, flags=re.I).strip()
        if cleaned:
            return cleaned
    return ""


def _looks_like_table_header(value: str) -> bool:
    lower = value.lower()
    header_words = ("ilość", "ilosc", "jedn", "cena", "netto", "vat", "brutto", "wartość", "wartosc")
    return sum(word in lower for word in header_words) >= 2
