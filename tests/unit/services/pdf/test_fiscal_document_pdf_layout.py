"""Unit test PDF fattura elettronew + i18n."""
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace

import pytest

from src.services.pdf.fiscal_document_pdf_layout import FiscalDocumentPDFLayout
from src.services.pdf.fiscal_document_pdf_service import FiscalDocumentPDFService
from src.services.pdf.i18n.invoice_pdf_labels import (
    DEFAULT_PRE_INVOICE_DISCLAIMER,
    get_invoice_labels,
)
from src.services.pdf.i18n.locale_resolver import (
    resolve_country_iso,
    resolve_invoice_locale,
)


def _pdf_text(pdf_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _address(iso="IT", country_name="Italia", **kwargs):
    defaults = {
        "firstname": "",
        "lastname": "",
        "company": "Test Company Srl",
        "address1": "Via Roma 1",
        "address2": "",
        "postcode": "00100",
        "city": "Roma",
        "state": "RM",
        "phone": "061234567",
        "mobile_phone": "3331234567",
        "vat": "IT12345678901",
        "dni": None,
        "country": SimpleNamespace(iso_code=iso, name=country_name),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _minimal_context(locale="it", n_details=2, tax_note=None):
    labels = get_invoice_labels(locale)
    details = []
    for i in range(n_details):
        details.append(
            {
                "product_reference": f"SKU{i:03d}",
                "product_name": f"Prodotto di test numero {i} descrizione lunga",
                "product_qty": 1 + i,
                "unit_price_net": 10.0 + i,
                "total_price_net": (10.0 + i) * (1 + i),
                "reduction_percent": 0.0,
                "vat_rate": 22.0 if locale == "it" else 0.0,
                "tax_note": tax_note,
            }
        )
    merchandise = sum(d["total_price_net"] for d in details)
    return {
        "company_config": {
            "company_name": "Web Market s.r.l.",
            "address": "Corso Vittorio Emanuele, 110/5",
            "postal_code": "80121",
            "city": "Napoli",
            "province": "NA",
            "vat_number": "IT08632861210",
            "fiscal_code": "08632861210",
            "iban": "IT79A0306939845100000014622",
            "bic_swift": "BCITITMM",
        },
        "logo_path": None,
        "labels": labels,
        "locale": locale,
        "doc_number": "9748",
        "doc_date": "15/07/2026",
        "is_credit_note": False,
        "credit_note_ref_number": None,
        "credit_note_ref_date": None,
        "credit_note_reason": None,
        "invoice_address": _address(
            iso="IT" if locale == "it" else "FR",
            country_name="Italia" if locale == "it" else "Francia",
        ),
        "delivery_address": _address(
            iso="IT" if locale == "it" else "FR",
            country_name="Italia" if locale == "it" else "Francia",
        ),
        "order_reference": "509488/W",
        "order_date": datetime(2026, 7, 14),
        "details": details,
        "totals": {
            "merchandise_net": merchandise,
            "shipping_incl": 37.99,
            "shipping_excl": 31.14,
            "taxable_total": merchandise + 31.14,
            "collection_fee": 0.0,
            "merchandise_gross": merchandise * 1.22,
            "total_vat": merchandise * 0.22 + 6.85,
            "misc_fee": 0.0,
            "doc_total": merchandise * 1.22 + 37.99,
            "total_weight": 80.546,
        },
        "vat_summary": [
            {
                "rate": 22.0 if locale == "it" else 0.0,
                "merchandise": merchandise,
                "shipping": 31.14,
                "vat": merchandise * 0.22 if locale == "it" else 0.0,
            }
        ],
        "payment_name": "PayPal",
        "deadlines_text": "",
        "notes_text": DEFAULT_PRE_INVOICE_DISCLAIMER,
        "packages": 1,
    }


class TestLocaleResolver:
    def test_resolve_invoice_locale_it(self):
        assert resolve_invoice_locale("IT") == "it"
        assert resolve_invoice_locale(None) == "it"

    def test_resolve_invoice_locale_mapped(self):
        assert resolve_invoice_locale("FR") == "fr"
        assert resolve_invoice_locale("DE") == "de"
        assert resolve_invoice_locale("AT") == "de"
        assert resolve_invoice_locale("ES") == "es"
        assert resolve_invoice_locale("GB") == "en"

    def test_resolve_invoice_locale_unknown_defaults_en(self):
        assert resolve_invoice_locale("NL") == "en"
        assert resolve_invoice_locale("PL") == "en"

    def test_resolve_country_iso(self):
        inv = _address(iso="FR", country_name="Francia")
        assert resolve_country_iso(inv, None) == "FR"
        assert resolve_country_iso(None, inv) == "FR"
        assert resolve_country_iso(None, None) is None


class TestInvoiceLabels:
    def test_all_locales_have_required_keys(self):
        required = {
            "doc_title",
            "credit_note_title",
            "billing",
            "delivery",
            "item_headers",
            "doc_total",
            "notes_title",
            "page_footer",
        }
        for loc in ("it", "fr", "de", "es", "en"):
            labels = get_invoice_labels(loc)
            assert required.issubset(labels.keys()), loc
            assert len(labels["item_headers"]) == 7

    def test_italian_and_french_titles(self):
        assert get_invoice_labels("it")["doc_title"] == "FATTURA"
        assert get_invoice_labels("fr")["doc_title"] == "FACTURE"
        assert get_invoice_labels("de")["doc_title"] == "RECHNUNG"
        assert get_invoice_labels("es")["doc_title"] == "FACTURA"
        assert get_invoice_labels("en")["doc_title"] == "INVOICE"

    def test_page_footer_templates(self):
        assert "Pagina" in get_invoice_labels("it")["page_footer"]
        assert "page" in get_invoice_labels("fr")["page_footer"]
        assert get_invoice_labels("unknown")["doc_title"] == "FATTURA"  # fallback IT


class TestFiscalDocumentPDFLayout:
    def test_render_it_produces_pdf(self):
        ctx = _minimal_context("it")
        out = FiscalDocumentPDFLayout.render_document(ctx)
        assert isinstance(out, (bytes, bytearray))
        assert out[:4] == b"%PDF"
        assert len(out) > 500

    def test_render_fr_produces_pdf(self):
        ctx = _minimal_context("fr")
        ctx["doc_number"] = "9762"
        out = FiscalDocumentPDFLayout.render_document(ctx)
        assert out[:4] == b"%PDF"

    def test_notes_contain_disclaimer(self):
        ctx = _minimal_context("it")
        out = FiscalDocumentPDFLayout.render_document(ctx)
        text = _pdf_text(out)
        assert "art. 21" in text or "DPR 633" in text or "pre-fattura" in text

    def test_notes_append_tax_normative(self):
        tax_note = "operazione non imponibile ai sensi dell'art. 41 D.L. 331/1993"
        ctx = _minimal_context("fr", tax_note=tax_note)
        ctx["notes_text"] = f"{DEFAULT_PRE_INVOICE_DISCLAIMER} {tax_note}"
        out = FiscalDocumentPDFLayout.render_document(ctx)
        text = _pdf_text(out)
        assert "331" in text or "non imponibile" in text

    def test_multipage_with_many_rows(self):
        ctx = _minimal_context("it", n_details=40)
        out = FiscalDocumentPDFLayout.render_document(ctx)
        assert out[:4] == b"%PDF"
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(out))
        assert len(reader.pages) >= 2

    def test_credit_note_title_and_ref(self):
        ctx = _minimal_context("it")
        ctx["is_credit_note"] = True
        ctx["credit_note_ref_number"] = "9000"
        ctx["credit_note_ref_date"] = "01/07/2026"
        ctx["credit_note_reason"] = "Reso merce"
        out = FiscalDocumentPDFLayout.render_document(ctx)
        text = _pdf_text(out)
        assert "NOTA DI CREDITO" in text or "CREDITO" in text
        assert "9000" in text


class TestFiscalDocumentPDFService:
    def test_build_notes_default_disclaimer(self):
        text = FiscalDocumentPDFService._build_notes_text(
            invoice_pdf_config={},
            details=[],
        )
        assert "art. 21 DPR 633/72" in text

    def test_build_notes_appends_tax_note(self):
        text = FiscalDocumentPDFService._build_notes_text(
            invoice_pdf_config={"append_tax_normative": "true"},
            details=[
                {"tax_note": "operazione non imponibile ai sensi dell'art. 41"},
                {"tax_note": "operazione non imponibile ai sensi dell'art. 41"},
            ],
        )
        assert text.count("operazione non imponibile") == 1

    def test_build_notes_skips_append_when_disabled(self):
        text = FiscalDocumentPDFService._build_notes_text(
            invoice_pdf_config={"append_tax_normative": "false"},
            details=[{"tax_note": "art. 41"}],
        )
        assert "art. 41" not in text

    def test_generate_pdf_end_to_end(self):
        svc = FiscalDocumentPDFService()
        fiscal = SimpleNamespace(
            document_type="invoice",
            document_number="9748",
            internal_number=None,
            date_add=datetime(2026, 7, 15),
            id_store=None,
            total_price_with_tax=660.40,
            credit_note_reason=None,
        )
        order = SimpleNamespace(
            reference="509488/W",
            id_order=1,
            date_add=datetime(2026, 7, 14),
            payment_due_date=None,
            products_total_price_net=510.17,
            total_price_with_tax=660.40,
            total_weight=80.546,
            shipments=SimpleNamespace(
                price_tax_excl=31.14,
                price_tax_incl=37.99,
                id_tax=None,
            ),
        )
        details = [
            {
                "product_reference": "BTI JW4004",
                "product_name": "Invertitore basculante",
                "product_qty": 1,
                "unit_price_net": 9.59,
                "total_price_net": 9.30,
                "reduction_percent": 3.0,
                "vat_rate": 22.0,
            }
        ]
        company = {
            "company_name": "Web Market s.r.l.",
            "address": "Corso Vittorio Emanuele",
            "postal_code": "80121",
            "city": "Napoli",
            "province": "NA",
            "vat_number": "IT08632861210",
            "fiscal_code": "08632861210",
            "iban": "IT79A0306939845100000014622",
            "bic_swift": "BCITITMM",
        }
        out = svc.generate_pdf(
            fiscal_document=fiscal,
            order=order,
            invoice_address=_address(),
            delivery_address=_address(),
            details_with_products=details,
            payment_name="PayPal",
            company_config=company,
            invoice_pdf_config={},
        )
        assert out[:4] == b"%PDF"

    def test_vat_summary_uses_detail_rate_not_zero_when_shipping_22(self):
        """Regressione fattura 000016/ordine 69057: merce snapshot 22% + spedizione 22% → un bucket."""
        svc = FiscalDocumentPDFService()
        fiscal = SimpleNamespace(total_price_with_tax=2816.965)
        order = SimpleNamespace(
            products_total_price_net=2244.24,
            total_price_with_tax=2816.965,
            total_weight=0,
            shipments=SimpleNamespace(
                price_tax_excl=64.75,
                price_tax_incl=79.0,
                id_tax=217,
            ),
        )
        details = [
            {
                "total_price_net": 2244.24,
                "vat_rate": 22.0,  # da FiscalDocumentDetail.id_tax (non OrderDetail VIES 0%)
            }
        ]

        class _TaxRepo:
            def get_percentage_by_id(self, id_tax):
                return 22.0 if id_tax == 217 else 0.0

        class _DB:
            pass

        # monkeypatch TaxRepository via local import path used in _compute_totals
        import src.services.pdf.fiscal_document_pdf_service as mod
        from unittest.mock import patch

        with patch(
            "src.repository.tax_repository.TaxRepository",
            return_value=_TaxRepo(),
        ):
            totals, vat_summary = svc._compute_totals(
                fiscal_document=fiscal,
                order=order,
                details=details,
                db=_DB(),
            )

        assert len(vat_summary) == 1
        assert vat_summary[0]["rate"] == 22.0
        assert vat_summary[0]["merchandise"] == pytest.approx(2244.24)
        assert vat_summary[0]["shipping"] == pytest.approx(64.75)
        assert vat_summary[0]["vat"] == pytest.approx(507.9778)
        assert totals["doc_total"] == pytest.approx(2816.965)
        assert totals["total_vat"] == pytest.approx(507.9778)
