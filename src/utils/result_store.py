'''
Simple result store for capturing process outputs.
'''

# Global store for process results
_results = {}


def store_result(session_id: str, data: dict) -> None:
    '''
    Store result data for a session.
    
    Args:
        session_id: Session identifier
        data: Result data to store
    '''
    _results[session_id] = data


def get_result(session_id: str) -> dict | None:
    '''
    Get result data for a session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Result data if found, None otherwise
    '''
    return _results.get(session_id)


def clear_result(session_id: str) -> None:
    '''
    Clear result data for a session.
    
    Args:
        session_id: Session identifier
    '''
    if session_id in _results:
        del _results[session_id]

