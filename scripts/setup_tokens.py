#!/usr/bin/env python3.11
"""Simple script to re-initialize Schwab API tokens."""

import sys
import os
from pathlib import Path

# Add the project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.config_schwab import SchwabConfig
from utils.logging import setup_logging

def main():
    """Re-initialize Schwab API tokens."""
    logger = setup_logging(level="INFO")
    
    # Load configuration
    config = SchwabConfig.from_env()
    
    if not config.is_valid():
        logger.error("Schwab API credentials required!")
        logger.error("Set environment variables SCHWAB_APP_KEY and SCHWAB_APP_SECRET")
        logger.error("Or create a .env file with app_key and app_secret")
        return 1
    
    # Remove existing token file to force fresh authentication
    token_file = Path(config.token_path)
    if token_file.exists():
        logger.info(f"🗑️  Removing existing token file: {token_file}")
        token_file.unlink()
    
    # Ensure the auth directory exists
    token_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        import schwabdev
        logger.info("🔐 Starting fresh Schwab authentication...")
        logger.info("This will open a browser window for OAuth authentication.")
        
        client = schwabdev.Client(
            app_key=config.app_key,
            app_secret=config.app_secret,
            callback_url=config.redirect_uri,
            tokens_file=config.token_path
        )
        
        logger.info("✓ Authentication completed successfully!")
        logger.info(f"✓ Tokens saved to: {config.token_path}")
        logger.info("✓ You can now run 'python3.11 main.py' to use the real API")
        
    except ImportError:
        logger.error("schwabdev package is required!")
        logger.error("Install with: pip install schwabdev")
        return 1
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())