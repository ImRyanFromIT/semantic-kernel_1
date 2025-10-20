"""
Production run script for SRM Archivist Agent.

This script runs the agent in live mode with Microsoft Graph API integration.
The agent will continuously monitor Sparky@greatvaluelab.com and process
incoming SRM requests automatically.

Usage:
    From project root:
        python agent/run_live_agent.py
    
    OR from agent directory:
        python run_live_agent.py
"""

import asyncio
import sys
import logging
import os
from pathlib import Path

# Ensure we can import from agent package
# Add project root to path if not already there
current_dir = Path(__file__).parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Change to agent directory for relative file paths
os.chdir(current_dir)

from agent.main import SrmArchivistAgent


async def main():
    """
    Main entry point for production agent.
    
    Runs the agent in live mode with continuous email monitoring.
    """
    # Create logger
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("="*60)
        logger.info("Starting SRM Archivist Agent - LIVE MODE")
        logger.info("="*60)
        
        # Verify environment configuration
        from agent.config import load_config, validate_config
        
        logger.info("Loading configuration...")
        config = load_config("agent_config.yaml")
        
        # Validate configuration
        issues = validate_config(config)
        if issues:
            logger.error("Configuration validation failed:")
            for issue in issues:
                logger.error(f"  - {issue}")
            logger.error("\nPlease fix configuration issues before running the agent.")
            sys.exit(1)
        
        logger.info("Configuration validated successfully")
        logger.info(f"Mailbox: {config.graph_api.mailbox}")
        logger.info(f"Support Team: {config.support_team_email}")
        logger.info(f"Scan Interval: {config.email_scan_interval_seconds} seconds")
        logger.info(f"Update Mode: {'LIVE' if not config.mock_updates else 'MOCK'}")
        logger.info("-"*60)
        
        # Create and initialize agent in LIVE mode
        agent = SrmArchivistAgent(
            config_file="agent_config.yaml",
            test_mode=False  # Force live mode
        )
        
        logger.info("Initializing agent...")
        initialized = await agent.initialize()
        
        if not initialized:
            logger.error("Failed to initialize agent")
            sys.exit(1)
        
        logger.info("Agent initialized successfully")
        logger.info("="*60)
        logger.info("AGENT IS NOW RUNNING")
        logger.info("Press Ctrl+C to stop")
        logger.info("="*60)
        
        # Run agent monitoring loop
        await agent.run()
        
    except KeyboardInterrupt:
        logger.info("\nShutdown requested by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Agent stopped")


if __name__ == "__main__":
    # Setup logging before running - ensure log file is in state directory
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

