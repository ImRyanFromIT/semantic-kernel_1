"""
Demo run script for SRM Archivist Agent.

This script runs the agent in DEMO/TEST mode using local test emails
instead of connecting to Microsoft Graph API. Perfect for demonstrations
and testing without affecting production email.

Usage:
    From project root:
        python agent/run_demo_agent.py
    
    OR from agent directory:
        python run_demo_agent.py
"""

import asyncio
import sys
import logging
import os
from pathlib import Path

# Ensure we can import from agent package
current_dir = Path(__file__).parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Change to agent directory for relative file paths
os.chdir(current_dir)

from agent.main import SrmArchivistAgent


async def main():
    """
    Main entry point for demo agent.
    
    Runs the agent in test mode with file-based email reading.
    """
    # Create logger
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("="*60)
        logger.info("Starting SRM Archivist Agent - DEMO MODE")
        logger.info("="*60)
        logger.info("Using test emails from: test_emails/Inbox/")
        logger.info("No actual emails will be sent (mocked)")
        logger.info("="*60)
        
        # Verify environment configuration
        from agent.config import load_config, validate_config
        
        logger.info("Loading configuration...")
        config = load_config("agent_config.yaml")
        
        # Validate configuration (but some things can be missing in test mode)
        issues = validate_config(config)
        if issues:
            logger.warning("Configuration has some issues (acceptable in demo mode):")
            for issue in issues:
                logger.warning(f"  - {issue}")
        
        logger.info(f"Update Mode: {'LIVE UPDATES' if not config.mock_updates else 'MOCK UPDATES'}")
        logger.info(f"Scan Interval: {config.email_scan_interval_seconds} seconds")
        logger.info("-"*60)
        
        # Create agent in TEST mode
        agent = SrmArchivistAgent(
            config_file="agent_config.yaml",
            test_mode=True  # Force test mode - reads from test_emails/Inbox/
        )
        
        logger.info("Starting agent in autonomous demo mode...")
        logger.info("="*60)
        logger.info("DEMO AGENT IS NOW RUNNING")
        logger.info("The agent will process emails from test_emails/Inbox/")
        logger.info("Press Ctrl+C to stop")
        logger.info("="*60)
        
        # Run agent monitoring loop (will initialize internally)
        await agent.run()
        
    except KeyboardInterrupt:
        logger.info("\nShutdown requested by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Demo agent stopped")


if __name__ == "__main__":
    # Setup logging before running
    from pathlib import Path
    agent_dir = Path(__file__).parent
    state_dir = agent_dir / 'state'
    state_dir.mkdir(exist_ok=True)
    log_file = state_dir / 'agent_actions.log'
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(str(log_file)),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Run the async main function
    asyncio.run(main())


