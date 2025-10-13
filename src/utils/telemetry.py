'''
Simple telemetry logging for process events.
'''

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any


class TelemetryLogger:
    '''
    Simple JSONL logger for telemetry events.
    
    Logs events to a JSONL file for easy analysis with grep/jq.
    '''
    
    def __init__(self, log_dir: str = "logs"):
        '''
        Initialize the telemetry logger.
        
        Args:
            log_dir: Directory to store log files
        '''
        from src.utils.debug_config import is_debug
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create log file with date
        date_str = datetime.now().strftime("%Y%m%d")
        self.log_file = self.log_dir / f"events_{date_str}.jsonl"
        
        # Set up Python logger
        self.logger = logging.getLogger("telemetry")
        self.logger.setLevel(logging.INFO)
        
        # Console handler - only add if debug mode is enabled
        if is_debug():
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
    
    def emit(self, event: dict[str, Any]) -> None:
        '''
        Emit a telemetry event.
        
        Args:
            event: Dictionary containing event data
        '''
        # Add timestamp if not present
        if 'ts' not in event:
            event['ts'] = datetime.now().isoformat()
        
        try:
            # Write to JSONL file
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event) + '\n')
        except Exception as e:
            # Never fail user request if logging fails
            self.logger.warning(f"Failed to write telemetry event: {e}")
    
    def log_router_classified(
        self, 
        session_id: str, 
        intent: str, 
        confidence: float,
        query: str
    ) -> None:
        '''Log when router classifies an intent.'''
        self.emit({
            'event_type': 'router_classified',
            'session_id': session_id,
            'intent': intent,
            'confidence': confidence,
            'query': query,
        })
    
    def log_process_state_change(
        self, 
        session_id: str, 
        process: str, 
        from_state: str, 
        to_state: str,
        latency_ms: float = 0
    ) -> None:
        '''Log process state transitions.'''
        self.emit({
            'event_type': 'process_state_change',
            'session_id': session_id,
            'process': process,
            'from_state': from_state,
            'to_state': to_state,
            'latency_ms': latency_ms,
        })
    
    def log_answer_published(
        self, 
        session_id: str, 
        selected_id: str | None, 
        confidence: float,
        alternatives_count: int = 0
    ) -> None:
        '''Log when an answer is published to the user.'''
        self.emit({
            'event_type': 'answer_published',
            'session_id': session_id,
            'selected_id': selected_id,
            'confidence': confidence,
            'alts_count': alternatives_count,
        })
    
    def log_error(
        self, 
        session_id: str, 
        error_code: str, 
        error_message: str,
        context: dict | None = None
    ) -> None:
        '''Log errors during processing.'''
        event = {
            'event_type': 'error',
            'session_id': session_id,
            'error_code': error_code,
            'error_message': error_message,
        }
        if context:
            event['context'] = context
        self.emit(event)
    
    def log_input_rejected(
        self,
        session_id: str,
        user_query: str,
        rejection_reason: str
    ) -> None:
        '''
        Log when user input is rejected by validation guardrails.
        
        Args:
            session_id: Session identifier
            user_query: The rejected user query
            rejection_reason: Reason for rejection
        '''
        self.emit({
            'event_type': 'input_rejected',
            'session_id': session_id,
            'user_query': user_query,
            'rejection_reason': rejection_reason,
        })

