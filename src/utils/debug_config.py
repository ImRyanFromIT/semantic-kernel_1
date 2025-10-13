'''
Debug configuration module for controlling verbose output.

This module provides a centralized way to manage debug mode across the application.
'''


# Global debug state
_DEBUG_ENABLED = False


def set_debug(enabled: bool) -> None:
    '''
    Set the global debug mode.
    
    Args:
        enabled: True to enable debug output, False to disable
    '''
    global _DEBUG_ENABLED
    _DEBUG_ENABLED = enabled


def is_debug() -> bool:
    '''
    Check if debug mode is enabled.
    
    Returns:
        True if debug mode is enabled, False otherwise
    '''
    return _DEBUG_ENABLED


def debug_print(*args, **kwargs) -> None:
    '''
    Print debug output only if debug mode is enabled.
    
    Args:
        *args: Positional arguments to pass to print()
        **kwargs: Keyword arguments to pass to print()
    '''
    if _DEBUG_ENABLED:
        print(*args, **kwargs)

