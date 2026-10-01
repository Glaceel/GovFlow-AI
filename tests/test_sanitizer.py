"""
GovFlow AI — Sanitizer tests.

Tests deterministic PII masking for NIK, phone numbers, and email addresses.
"""
import pytest
from app.services.sanitizer import sanitize


# ---------------------------------------------------------------------------
# NIK masking
# ---------------------------------------------------------------------------

class TestNIKMasking:
    def test_plain_16_digit_nik(self):
        text = "NIK saya adalah 3273012505900003 mohon diverifikasi."
        result = sanitize(text)
        assert "3273012505900003" not in result
        assert "[NIK_MASKED]" in result

    def test_nik_with_spaces(self):
        text = "NIK: 327301 250590 0003"
        result = sanitize(text)
        assert "327301" not in result
        assert "[NIK_MASKED]" in result

    def test_non_nik_short_number_preserved(self):
        """A 6-digit number should NOT be masked as a NIK."""
        text = "Kode pos saya 40123."
        result = sanitize(text)
        assert "40123" in result
        assert "[NIK_MASKED]" not in result

    def test_multiple_niks(self):
        text = "NIK A: 3273012505900003 dan NIK B: 1234567890123456"
        result = sanitize(text)
        assert "3273012505900003" not in result
        assert "1234567890123456" not in result
        assert result.count("[NIK_MASKED]") == 2


# ---------------------------------------------------------------------------
# Phone masking
# ---------------------------------------------------------------------------

class TestPhoneMasking:
    def test_local_format_08(self):
        text = "Hubungi saya di 081234567890."
        result = sanitize(text)
        assert "081234567890" not in result
        assert "[PHONE_MASKED]" in result

    def test_local_format_0812(self):
        text = "No HP: 08123456789"
        result = sanitize(text)
        assert "08123456789" not in result
        assert "[PHONE_MASKED]" in result

    def test_international_format_plus62(self):
        text = "WhatsApp: +6281234567890"
        result = sanitize(text)
        assert "+6281234567890" not in result
        assert "[PHONE_MASKED]" in result

    def test_international_format_with_spaces(self):
        text = "Tel: +62 812 3456 7890"
        result = sanitize(text)
        assert "812" not in result or "[PHONE_MASKED]" in result

    def test_short_number_not_masked(self):
        """A 5-digit number should not be masked as a phone."""
        text = "Kode area 40123"
        result = sanitize(text)
        assert "[PHONE_MASKED]" not in result


# ---------------------------------------------------------------------------
# Email masking
# ---------------------------------------------------------------------------

class TestEmailMasking:
    def test_simple_email(self):
        text = "Email saya budi@example.com untuk konfirmasi."
        result = sanitize(text)
        assert "budi@example.com" not in result
        assert "[EMAIL_MASKED]" in result

    def test_email_with_subdomain(self):
        text = "Kirim ke kepala@dinas.bandung.go.id"
        result = sanitize(text)
        assert "kepala@dinas.bandung.go.id" not in result
        assert "[EMAIL_MASKED]" in result

    def test_email_with_plus_sign(self):
        text = "user+tag@mail.com"
        result = sanitize(text)
        assert "user+tag@mail.com" not in result
        assert "[EMAIL_MASKED]" in result

    def test_no_false_positive_on_at_sign_in_text(self):
        """Plain @ not followed by a domain should not trigger masking."""
        text = "Tanya @ kantor besok."
        result = sanitize(text)
        assert "[EMAIL_MASKED]" not in result


# ---------------------------------------------------------------------------
# Combined / order-of-operations
# ---------------------------------------------------------------------------

class TestCombinedSanitization:
    def test_all_pii_types_in_one_text(self):
        text = (
            "Nama: Budi, NIK 3273012505900003, "
            "HP 081234567890, email budi@example.com. "
            "Komplain tentang jalan rusak."
        )
        result = sanitize(text)
        assert "3273012505900003" not in result
        assert "081234567890" not in result
        assert "budi@example.com" not in result
        assert "jalan rusak" in result  # non-PII content preserved

    def test_empty_text(self):
        assert sanitize("") == ""

    def test_text_with_no_pii(self):
        text = "Jalan di depan rumah saya berlubang besar."
        result = sanitize(text)
        assert result == text
