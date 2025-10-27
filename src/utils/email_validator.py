"""
Email validation utility for domain-restricted notifications.
"""

import re
from typing import List, Tuple


def validate_email_format(email: str) -> bool:
    """
    Validate basic email format using regex.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if email format is valid, False otherwise
    """
    # Basic email regex pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))


def validate_email_domain(email: str, allowed_domain: str = "greatvaluelab.com") -> bool:
    """
    Validate that email belongs to allowed domain.
    
    Args:
        email: Email address to validate
        allowed_domain: Allowed domain (default: greatvaluelab.com)
        
    Returns:
        True if email domain matches allowed_domain, False otherwise
    """
    if not validate_email_format(email):
        return False
    
    email = email.strip().lower()
    domain = email.split('@')[-1]
    
    return domain == allowed_domain.lower()


def validate_email_list(emails: List[str], allowed_domain: str = "greatvaluelab.com") -> Tuple[List[str], List[str]]:
    """
    Validate a list of email addresses against allowed domain.
    
    Args:
        emails: List of email addresses to validate
        allowed_domain: Allowed domain (default: greatvaluelab.com)
        
    Returns:
        Tuple of (valid_emails, invalid_emails)
    """
    valid = []
    invalid = []
    
    for email in emails:
        email = email.strip()
        if not email:
            continue
            
        if validate_email_domain(email, allowed_domain):
            valid.append(email)
        else:
            invalid.append(email)
    
    return valid, invalid


def parse_email_recipients(recipients_str: str) -> List[str]:
    """
    Parse comma-separated email recipients string.
    
    Args:
        recipients_str: Comma-separated email addresses
        
    Returns:
        List of trimmed email addresses
    """
    if not recipients_str:
        return []
    
    # Split by comma and filter empty strings
    emails = [email.strip() for email in recipients_str.split(',') if email.strip()]
    
    return emails

