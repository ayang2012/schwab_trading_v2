#!/usr/bin/env python3
"""CLI tool for managing option assignments."""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

try:
    from api.client import RealBrokerClient
    from utils.config_schwab import SchwabConfig
    from utils.logging import setup_logging
    from utils.assignments import fetch_and_record_assignments, get_assignment_impact_on_positions
    from utils.db_utils import AssignmentDB
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)


def cmd_backfill(args):
    """Backfill assignments from historical data."""
    logger = setup_logging(level=args.log_level)
    
    # Initialize client
    config = SchwabConfig.from_env()
    if not config.is_valid():
        config.app_key = "ER0kVS2P0U9WMMlRRt7Mw4ELCmVRwTB5"
        config.app_secret = "3mJejG1MBpISgcjj"
    
    try:
        client = RealBrokerClient(
            app_key=config.app_key,
            app_secret=config.app_secret,
            redirect_uri=config.redirect_uri,
            token_path=config.token_path
        )
        logger.info("✓ Schwab client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize client: {e}")
        return 1
    
    # Calculate lookback period
    since = None
    if args.days:
        since = datetime.now() - timedelta(days=args.days)
        logger.info(f"Backfilling assignments from {since.date()} ({args.days} days)")
    
    # Fetch and record assignments
    db = AssignmentDB(args.db_path)
    try:
        assignments = fetch_and_record_assignments(
            client, 
            db, 
            since=since,
            lookback_days=args.days or 30
        )
        
        if assignments:
            logger.info(f"✅ Recorded {len(assignments)} new assignments")
            for assignment in assignments:
                logger.info(
                    f"  - {assignment['ticker']}: {assignment['shares']} shares "
                    f"at ${assignment['price_per_share']:.2f} on {assignment['assigned_at'][:10]}"
                )
        else:
            logger.info("No new assignments found")
        
        return 0
        
    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        return 1


def cmd_status(args):
    """Show assignment status and statistics."""
    logger = setup_logging(level=args.log_level)
    
    db = AssignmentDB(args.db_path)
    
    try:
        # Get summary statistics
        summary = db.get_assignment_summary()
        
        print("📊 ASSIGNMENT TRACKING STATUS")
        print("=" * 50)
        print(f"Total assignments recorded: {summary['total_assignments']}")
        print(f"Recent assignments (30d): {summary['recent_assignments_30d']}")
        print()
        
        if summary['assignments_by_ticker']:
            print("📈 ASSIGNMENTS BY TICKER:")
            for ticker_data in summary['assignments_by_ticker'][:10]:  # Top 10
                print(f"  {ticker_data['ticker']}: {ticker_data['count']} assignments, "
                      f"{ticker_data['total_shares']} total shares")
        
        # Show recent assignments if requested
        if args.recent:
            recent = db.get_recent_assignments(days=args.recent)
            if recent:
                print(f"\n🕐 RECENT ASSIGNMENTS ({args.recent} days):")
                for assignment in recent:
                    print(f"  {assignment['assigned_at'][:10]} - {assignment['ticker']}: "
                          f"{assignment['shares']} shares at ${assignment['price_per_share']:.2f}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Status command failed: {e}")
        return 1


def cmd_ticker(args):
    """Show assignment details for a specific ticker."""
    logger = setup_logging(level=args.log_level)
    
    db = AssignmentDB(args.db_path)
    ticker = args.ticker.upper()
    
    try:
        impact = get_assignment_impact_on_positions(ticker, db)
        
        print(f"📊 ASSIGNMENT IMPACT FOR {ticker}")
        print("=" * 50)
        print(f"Total assigned shares: {impact['assigned_shares']}")
        if impact['assigned_basis']:
            print(f"Average assigned basis: ${impact['assigned_basis']:.2f}")
            print(f"Total assigned cost: ${impact['total_assigned_cost']:,.2f}")
        else:
            print("No assigned basis recorded")
        print(f"Number of assignments: {impact['assignment_count']}")
        
        if impact['recent_assignments']:
            print(f"\n📈 ASSIGNMENT HISTORY:")
            for assignment in impact['recent_assignments']:
                print(f"  {assignment['assigned_at'][:10]} - {assignment['option_symbol']}: "
                      f"{assignment['shares']} shares at ${assignment['price_per_share']:.2f}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Ticker command failed: {e}")
        return 1


def cmd_check(args):
    """Check for new assignments and record them."""
    logger = setup_logging(level=args.log_level)
    
    # Initialize client
    config = SchwabConfig.from_env()
    if not config.is_valid():
        config.app_key = "ER0kVS2P0U9WMMlRRt7Mw4ELCmVRwTB5"
        config.app_secret = "3mJejG1MBpISgcjj"
    
    try:
        client = RealBrokerClient(
            app_key=config.app_key,
            app_secret=config.app_secret,
            redirect_uri=config.redirect_uri,
            token_path=config.token_path
        )
        logger.info("✓ Schwab client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize client: {e}")
        return 1
    
    # Check for new assignments
    db = AssignmentDB(args.db_path)
    try:
        assignments = fetch_and_record_assignments(
            client, 
            db, 
            lookback_days=args.lookback
        )
        
        if assignments:
            print(f"🚨 NEW ASSIGNMENTS DETECTED ({len(assignments)})")
            for assignment in assignments:
                print(f"  ⚠️  {assignment['ticker']}: {assignment['shares']} shares assigned")
                print(f"      Contract: {assignment['option_symbol']}")
                print(f"      Price: ${assignment['price_per_share']:.2f}")
                print(f"      Date: {assignment['assigned_at'][:10]}")
                print()
        else:
            print("✅ No new assignments detected")
        
        return 0
        
    except Exception as e:
        logger.error(f"Check command failed: {e}")
        return 1


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Option assignment tracking and management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s backfill --days 30              # Backfill last 30 days
  %(prog)s status --recent 7               # Show status with recent assignments
  %(prog)s ticker AAPL                     # Show AAPL assignment details
  %(prog)s check                           # Check for new assignments
        """
    )
    
    parser.add_argument("--db-path", default="data/assignments.db", 
                       help="Database path (default: data/assignments.db)")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
                       default="INFO", help="Logging level")
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Backfill command
    backfill_parser = subparsers.add_parser('backfill', help='Backfill historical assignments')
    backfill_parser.add_argument('--days', type=int, default=30,
                                help='Days to look back (default: 30)')
    backfill_parser.set_defaults(func=cmd_backfill)
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show assignment statistics')
    status_parser.add_argument('--recent', type=int, metavar='DAYS',
                              help='Show recent assignments from last N days')
    status_parser.set_defaults(func=cmd_status)
    
    # Ticker command
    ticker_parser = subparsers.add_parser('ticker', help='Show assignments for specific ticker')
    ticker_parser.add_argument('ticker', help='Stock ticker symbol')
    ticker_parser.set_defaults(func=cmd_ticker)
    
    # Check command
    check_parser = subparsers.add_parser('check', help='Check for new assignments')
    check_parser.add_argument('--lookback', type=int, default=3,
                             help='Days to look back for new assignments (default: 3)')
    check_parser.set_defaults(func=cmd_check)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == "__main__":
    exit(main())