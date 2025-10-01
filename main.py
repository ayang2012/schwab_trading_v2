"""v2 CLI entrypoint."""
import argparse
from pathlib import Path

try:
    # Try relative imports first (when run as module from parent)
    from .api.client import RealBrokerClient 
    from .api.sim_client import SimBrokerClient
    from .utils.config_schwab import SchwabConfig
    from .core.orchestrator import run_once
    from .utils.logging import setup_logging
except ImportError:
    # Fall back to direct imports (when run from within directory)
    from api.client import RealBrokerClient
    from api.sim_client import SimBrokerClient
    from utils.config_schwab import SchwabConfig
    from core.orchestrator import run_once
    from utils.logging import setup_logging


def main(argv=None):
    p = argparse.ArgumentParser(prog="v2-cli", description="Generate account snapshots from Schwab API")
    p.add_argument("--out", default="data/account", help="output directory")
    p.add_argument("--simulate", action="store_true", help="use simulated test data (default: real Schwab API)")
    p.add_argument("--app-key", help="Schwab API app key (or set SCHWAB_APP_KEY env var)")
    p.add_argument("--app-secret", help="Schwab API app secret (or set SCHWAB_APP_SECRET env var)")
    p.add_argument("--quiet", "-q", action="store_true", help="quiet mode - only show final results")
    p.add_argument("--verbose", "-v", action="store_true", help="verbose mode - show detailed API interactions")
    p.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO", help="set logging level")
    p.add_argument("--no-technicals", action="store_true", help="skip technical analysis (default: include technicals)")
    # Default to including technicals
    args = p.parse_args(argv)

    # Set up logging based on arguments
    if args.verbose:
        log_level = "DEBUG"
    elif args.quiet:
        log_level = "ERROR"
    else:
        log_level = args.log_level
    
    logger = setup_logging(level=log_level, quiet=args.quiet)

    if args.simulate:
        # Use simulated data for testing
        client = SimBrokerClient()
        logger.info("Using simulated test data (use without --simulate for real account data)")
    else:
        # Load Schwab configuration for real API usage (default behavior)
        config = SchwabConfig.from_env()
        
        # Override with command line args if provided
        if args.app_key:
            config.app_key = args.app_key
        if args.app_secret:
            config.app_secret = args.app_secret
        
        # Check if tokens file exists - if so, we can use saved credentials
        token_file = Path(config.token_path)
        if token_file.exists() and not config.is_valid():
            logger.debug(f"Using saved authentication from {config.token_path}")
            config.app_key = "ER0kVS2P0U9WMMlRRt7Mw4ELCmVRwTB5"  # Use your app key
            config.app_secret = "3mJejG1MBpISgcjj"  # Use your app secret
        
        if not config.is_valid():
            logger.error("Schwab API credentials required for real account data")
            logger.error("Either:")
            logger.error("1. Set environment variables:")
            logger.error("   export SCHWAB_APP_KEY='your_app_key'")
            logger.error("   export SCHWAB_APP_SECRET='your_app_secret'")
            logger.error("2. Use command line arguments:")
            logger.error("   --app-key your_app_key --app-secret your_app_secret")
            logger.error("3. Create .env file with app_key and app_secret")
            logger.error("4. Or use --simulate for test data")
            return 1
        
        try:
            client = RealBrokerClient(
                app_key=config.app_key,
                app_secret=config.app_secret,
                redirect_uri=config.redirect_uri,
                token_path=config.token_path
            )
        except Exception as e:
            logger.error(f"Error initializing Schwab client: {e}")
            logger.error("Make sure you have installed the required dependencies:")
            logger.error("  pip install schwabdev")
            return 1

    try:
        # Default to including technicals, unless --no-technicals is specified
        include_technicals = not args.no_technicals
        
        result = run_once(client, Path(args.out), include_technicals=include_technicals)
        logger.info(f"Wrote account snapshot: {result['file_path']}")
        
        # Now you can access the data programmatically if needed:
        # snapshot_data = result['data']
        # account_value = result['total_account_value']
        # etc.
        
    except Exception as e:
        logger.error(f"Error generating snapshot: {e}")
        return 1


if __name__ == "__main__":
    main()
