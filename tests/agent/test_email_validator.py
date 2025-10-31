"""
Email Validator Tests

Purpose: Test email validation utilities for domain-restricted notifications.

Type: Unit
Test Count: 10

Key Test Areas:
- Email format validation
- Domain validation
- Email list validation
- Email parsing

Dependencies:
- email_validator module
"""

import pytest
from src.utils.email_validator import (
    validate_email_format,
    validate_email_domain,
    validate_email_list,
    parse_email_recipients
)


class TestValidateEmailFormat:
    """Tests for validate_email_format function."""

    def test_valid_email_format(self):
        """Test that valid email formats pass validation."""
        assert validate_email_format("user@example.com") is True
        assert validate_email_format("test.user@company.co.uk") is True
        assert validate_email_format("name+tag@domain.org") is True

    def test_invalid_email_format(self):
        """Test that invalid email formats fail validation."""
        assert validate_email_format("invalid") is False
        assert validate_email_format("@example.com") is False
        assert validate_email_format("user@") is False
        assert validate_email_format("user @example.com") is False


class TestValidateEmailDomain:
    """Tests for validate_email_domain function."""

    def test_valid_domain(self):
        """Test that emails from allowed domain pass validation."""
        assert validate_email_domain("user@greatvaluelab.com", "greatvaluelab.com") is True
        assert validate_email_domain("USER@GREATVALUELAB.COM", "greatvaluelab.com") is True

    def test_invalid_domain(self):
        """Test that emails from other domains fail validation."""
        assert validate_email_domain("user@otherdomain.com", "greatvaluelab.com") is False
        assert validate_email_domain("user@example.com", "greatvaluelab.com") is False

    def test_invalid_format_returns_false(self):
        """Test that invalid email format returns False (covers line 36)."""
        assert validate_email_domain("invalid-email", "greatvaluelab.com") is False
        assert validate_email_domain("@greatvaluelab.com", "greatvaluelab.com") is False

    def test_default_domain(self):
        """Test that default domain is greatvaluelab.com."""
        assert validate_email_domain("user@greatvaluelab.com") is True
        assert validate_email_domain("user@otherdomain.com") is False


class TestValidateEmailList:
    """Tests for validate_email_list function."""

    def test_all_valid_emails(self):
        """Test validation of all valid emails."""
        emails = ["user1@greatvaluelab.com", "user2@greatvaluelab.com"]
        valid, invalid = validate_email_list(emails, "greatvaluelab.com")
        assert len(valid) == 2
        assert len(invalid) == 0

    def test_mixed_valid_and_invalid_emails(self):
        """Test validation of mixed email list."""
        emails = [
            "user@greatvaluelab.com",
            "spam@otherdomain.com",
            "test@greatvaluelab.com",
            "invalid-email"
        ]
        valid, invalid = validate_email_list(emails, "greatvaluelab.com")
        assert len(valid) == 2
        assert len(invalid) == 2
        assert "user@greatvaluelab.com" in valid
        assert "spam@otherdomain.com" in invalid

    def test_empty_string_in_list_skipped(self):
        """Test that empty strings are skipped (covers line 61)."""
        emails = ["user@greatvaluelab.com", "", "  ", "test@greatvaluelab.com"]
        valid, invalid = validate_email_list(emails, "greatvaluelab.com")
        assert len(valid) == 2
        assert len(invalid) == 0


class TestParseEmailRecipients:
    """Tests for parse_email_recipients function."""

    def test_parse_comma_separated_emails(self):
        """Test parsing comma-separated email list."""
        recipients_str = "user1@test.com, user2@test.com, user3@test.com"
        result = parse_email_recipients(recipients_str)
        assert len(result) == 3
        assert "user1@test.com" in result
        assert "user2@test.com" in result
        assert "user3@test.com" in result

    def test_parse_empty_string_returns_empty_list(self):
        """Test that empty string returns empty list (covers line 82)."""
        assert parse_email_recipients("") == []
        assert parse_email_recipients(None) == []

    def test_parse_with_extra_spaces(self):
        """Test that extra spaces are trimmed."""
        recipients_str = "  user1@test.com  ,  user2@test.com  "
        result = parse_email_recipients(recipients_str)
        assert len(result) == 2
        assert "user1@test.com" in result

    def test_parse_with_empty_entries(self):
        """Test that empty entries are filtered."""
        recipients_str = "user1@test.com,, ,user2@test.com"
        result = parse_email_recipients(recipients_str)
        assert len(result) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
