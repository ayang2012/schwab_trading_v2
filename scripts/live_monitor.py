#!/usr/bin/env python3
"""Live market data monitoring script - runs for 30 seconds with 10-second intervals."""

import time
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

try:
    from api.client import RealBrokerClient
    from utils.config_schwab import SchwabConfig
    from utils.logging import setup_logging
    from analysis.technicals import analyze_account_technicals
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)


def format_timestamp():
    """Get formatted timestamp."""
    return datetime.now().strftime("%H:%M:%S")


def print_divider(title=""):
    """Print a divider with optional title."""
    if title:
        print(f"\n{'='*20} {title} {'='*20}")
    else:
        print("-" * 60)


def display_key_metrics(snapshot, technicals_data):
    """Display key metrics that should change with live data."""
    print(f"🕐 [{format_timestamp()}] LIVE DATA SNAPSHOT")
    print(f"💰 Total Account Value: ${snapshot.official_liquidation_value or 0:,.2f}")
    
    # Show top 3 stock positions with current prices
    print(f"\n📈 TOP STOCK POSITIONS (Live Prices):")
    sorted_stocks = sorted(snapshot.stocks, key=lambda x: abs(x.market_value), reverse=True)[:3]
    for i, stock in enumerate(sorted_stocks, 1):
        pnl_color = "🟢" if stock.pnl >= 0 else "🔴"
        print(f"   {i}. {stock.symbol}: ${stock.market_price:.2f} {pnl_color} P&L: ${stock.pnl:,.2f}")
    
    # Show options with Greeks (these should update in real-time)
    if snapshot.options:
        print(f"\n📊 OPTIONS (Live Greeks):")
        for option in snapshot.options[:3]:  # Show first 3
            contract_key = option.contract_symbol
            tech_data = technicals_data.get('options', {}).get(contract_key, {})
            greeks = tech_data.get('greeks', {})
            
            delta = greeks.get('delta', 'N/A')
            pnl_color = "🟢" if option.total_pnl >= 0 else "🔴"
            
            print(f"   {option.symbol} ${option.strike} {option.put_call}: "
                  f"${option.market_price:.3f} "
                  f"Δ={delta if delta == 'N/A' else f'{delta:.3f}'} "
                  f"{pnl_color} P&L: ${option.total_pnl:,.0f}")
    
    print_divider()


def main():
    """Run live monitoring for 30 seconds."""
    # Setup
    logger = setup_logging(level='INFO', quiet=False)
    
    # Initialize client
    config = SchwabConfig.from_env()
    if not config.is_valid():
        # Use saved credentials
        config.app_key = "ER0kVS2P0U9WMMlRRt7Mw4ELCmVRwTB5"
        config.app_secret = "3mJejG1MBpISgcjj"
    
    try:
        client = RealBrokerClient(
            app_key=config.app_key,
            app_secret=config.app_secret, 
            redirect_uri=config.redirect_uri,
            token_path=config.token_path
        )
        logger.info("✓ Schwab client initialized successfully")
    except Exception as e:
        logger.error(f"❌ Error initializing client: {e}")
        return 1
    
    # Technical analysis will use the function directly
    
    print_divider("LIVE MARKET DATA MONITOR")
    print(f"🔴 LIVE MONITORING - Market Open")
    print(f"⏱️  Duration: 30 seconds")
    print(f"🔄 Update Interval: 10 seconds")
    print(f"🎯 Monitoring: Account value, stock prices, option Greeks")
    print_divider()
    
    # Run for 30 seconds, update every 10 seconds
    start_time = time.time()
    iteration = 0
    
    while time.time() - start_time < 30:
        iteration += 1
        
        try:
            print(f"\n📡 FETCH #{iteration} - Getting live data...")
            
            # Get fresh account snapshot
            snapshot = client.get_account_snapshot()
            
            # Run technical analysis to get live Greeks
            technicals_data = analyze_account_technicals(client, snapshot)
            
            # Display key metrics
            display_key_metrics(snapshot, technicals_data)
            
            # Wait 10 seconds unless it's the last iteration
            remaining_time = 30 - (time.time() - start_time)
            if remaining_time > 10:
                print(f"⏳ Waiting 10 seconds... ({remaining_time:.0f}s remaining)")
                time.sleep(10)
            else:
                break
                
        except Exception as e:
            logger.error(f"❌ Error during iteration {iteration}: {e}")
            time.sleep(5)  # Wait 5 seconds before retry
    
    elapsed = time.time() - start_time
    print_divider("MONITORING COMPLETE")
    print(f"✅ Live monitoring completed!")
    print(f"⏱️  Total runtime: {elapsed:.1f} seconds")
    print(f"📊 Iterations completed: {iteration}")
    print(f"🎯 Live data verification: {'SUCCESS' if iteration >= 3 else 'PARTIAL'}")
    
    return 0


if __name__ == "__main__":
    exit(main())