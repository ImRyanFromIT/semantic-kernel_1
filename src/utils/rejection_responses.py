'''
Rejection response formatting utilities.

Provides friendly, helpful messages when input is rejected by validation.
'''


def format_rejection_response(reason: str) -> str:
    '''
    Generate a polite rejection message with system guidance.
    
    Args:
        reason: The rejection category (e.g., 'too_short', 'gibberish', etc.)
        
    Returns:
        Formatted rejection message with examples and guidance
    '''
    rejection_messages = {
        'too_short': (
            "I didn't catch that. Could you please describe what you need help with? "
            "For example, you might say:\n"
            "  - 'I need to expand storage on a file share'\n"
            "  - 'How do I restore deleted files?'\n"
            "  - 'Need to add more CPU to a VM'\n\n"
            "Feel free to ask any question!"
        ),
        'too_long': (
            "Your message is quite long. Could you please provide a more concise description? "
            "Try to summarize your request in a sentence or two. "
            "For example:\n"
            "  - 'I need to expand storage on a file share'\n"
            "  - 'How do I restore deleted files?'\n"
            "  - 'Who handles backup requests?'"
        ),
        'gibberish': (
            "I'm having trouble understanding your request. "
            "I'm here to help with IT service requests like storage, backups, VMs, and more. "
            "Try asking something like:\n"
            "  - 'I need to add CPU to a VM'\n"
            "  - 'Who handles storage requests?'\n"
            "  - 'How does backup work?'\n\n"
            "Please describe what you'd like help with in a clear sentence."
        ),
        'nonsense': (
            "I can't help with that question as it doesn't seem to relate to IT services. "
            "I'm designed to assist with infrastructure and service requests such as:\n"
            "  - Storage and file share management\n"
            "  - VM and server resources\n"
            "  - Backup and recovery services\n"
            "  - Database administration\n\n"
            "How can I help with your IT service needs?"
        ),
        'spam_pattern': (
            "It looks like there might be an issue with your input. "
            "Please describe what you'd like help with in a clear sentence. "
            "I can assist with IT service requests and related questions. "
            "For example:\n"
            "  - 'I need to increase file share quota'\n"
            "  - 'Restore deleted files from last week'\n"
            "  - 'Create a new VM with 8 CPUs'"
        ),
        'excessive_special_chars': (
            "Your input contains too many special characters. "
            "Please describe your request using regular text. "
            "I'm here to help with IT service requests. "
            "For example:\n"
            "  - 'I need to expand storage'\n"
            "  - 'How do I restore files?'\n"
            "  - 'Need backup for new application'"
        ),
        'repetitive_content': (
            "It looks like there might be repetitive content in your message. "
            "Please describe what you need in a clear, concise way. "
            "I can help with questions like:\n"
            "  - 'I need to add storage to a file share'\n"
            "  - 'Who owns the production database?'\n"
            "  - 'How do I create a new VM?'"
        ),
        'invalid_content': (
            "I couldn't process your request. "
            "Please try rephrasing your question or request. "
            "I'm here to help with IT service needs. "
            "Examples:\n"
            "  - 'I need to expand storage on a file share'\n"
            "  - 'How do I restore deleted files?'\n"
            "  - 'Need more CPU resources'\n\n"
            "What can I help you with?"
        ),
    }
    
    # Return specific message or default
    return rejection_messages.get(
        reason,
        rejection_messages['invalid_content']
    )


def get_rejection_reason_from_validation(validation_result: str) -> str:
    '''
    Map validation result to rejection reason category.
    
    Args:
        validation_result: The validation result string (e.g., "INVALID: gibberish")
        
    Returns:
        Rejection reason category
    '''
    if 'INVALID:' in validation_result:
        # Extract reason from "INVALID: <reason>"
        reason_text = validation_result.split('INVALID:')[1].strip().lower()
        
        # Map to categories
        if 'nonsense' in reason_text:
            return 'nonsense'
        elif 'gibberish' in reason_text:
            return 'gibberish'
        elif 'spam' in reason_text or 'test' in reason_text:
            return 'spam_pattern'
        elif 'repetitive' in reason_text or 'repeated' in reason_text:
            return 'repetitive_content'
        else:
            return 'invalid_content'
    
    return 'invalid_content'

