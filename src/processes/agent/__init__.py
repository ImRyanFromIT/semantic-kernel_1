"""
Process definitions for the SRM Archivist Agent.

This package contains Semantic Kernel process definitions for email workflow automation.
"""

from .email_intake_process import EmailIntakeProcess
from .srm_help_process import SrmHelpProcess

__all__ = ["EmailIntakeProcess", "SrmHelpProcess"]
