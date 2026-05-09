from ksef_pdf_renamer.extractor import (
    InvoiceData,
    ensure_unique_filename,
    make_target_filename,
    sanitize_filename_part,
    _extract_invoice_number,
    _extract_issue_date,
    _extract_item_name,
    _extract_seller,
)


def sample_text() -> str:
    return """
    Faktura VAT nr FV/12/05/2026
    Data wystawienia: 2026-05-08

    Sprzedawca: ACME Polska Sp. z o.o.
    NIP 1234567890

    Nabywca: Klient Testowy Sp. z o.o.

    Lp. Nazwa towaru/usługi Ilość Cena netto VAT Wartość brutto
    1 Abonament KSeF Premium 1 szt 100,00 23% 123,00
    Razem 123,00
    """


def test_extract_fields_from_polish_invoice_text():
    text = sample_text()

    assert _extract_issue_date(text) == "2026-05-08"
    assert _extract_invoice_number(text) == "FV/12/05/2026"
    assert _extract_seller(text) == "ACME Polska Sp. z o.o."
    assert _extract_item_name(text) == "Abonament KSeF Premium"


def test_make_target_filename_sanitizes_unsafe_characters():
    data = InvoiceData(
        issue_date="2026-05-08",
        invoice_number="FV/12/05/2026",
        seller="ACME: Polska Sp. z o.o.",
        item_name="Usługa <testowa>",
    )

    assert make_target_filename(data) == "2026-05-08_FV 12 05 2026_ACME Polska Sp. z o.o_Usługa testowa.pdf"


def test_sanitize_filename_part_trims_long_values():
    assert len(sanitize_filename_part("a" * 120)) == 80


def test_ensure_unique_filename_adds_suffix():
    assert ensure_unique_filename("a.pdf", {"a.pdf", "a_2.pdf"}) == "a_3.pdf"
