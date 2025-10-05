#!/usr/bin/env python3
"""Generate fresh watchlist data using real market data (exactly like main.py does)."""

import sys
from pathlib import Path
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from live_monitor import analyze_watchlist_technicals
from api.client import RealBrokerClient
from api.sim_client import SimBrokerClient  
from utils.config_schwab import SchwabConfig
from config.settings import WATCHLIST_STOCKS
from analysis.technicals import get_technicals_for_symbol

def generate_fresh_watchlist():
    """Generate fresh watchlist data using real Schwab API (exactly like main.py does)."""
    
    print("🔍 Generating fresh watchlist data using real Schwab API...")
    
    # Use the exact same client initialization as main.py
    config = SchwabConfig.from_env()
    token_file = Path(config.token_path)
    if token_file.exists() and not config.is_valid():
        config.app_key = "ER0kVS2P0U9WMMlRRt7Mw4ELCmVRwTB5"
        config.app_secret = "3mJejG1MBpISgcjj"
    
    if not config.is_valid():
        print("❌ Schwab API credentials required")
        print("This script needs the same credentials that main.py uses")
        return None
    
    try:
        client = RealBrokerClient(
            app_key=config.app_key,
            app_secret=config.app_secret,
            redirect_uri=config.redirect_uri,
            token_path=config.token_path
        )
        print("✅ Using real Schwab API client (same as main.py)")
        client_type = "real"
    except Exception as e:
        print(f"❌ Error initializing Schwab client: {e}")
        print("Make sure you have the schwabdev package installed:")
        print("  pip install schwabdev")
        return None
    
    # Generate watchlist analysis using real client  
    print(f"� Analyzing {len(WATCHLIST_STOCKS)} watchlist symbols with real market data...")
    
    # Build the watchlist data structure manually using real client
    watchlist_stocks = {}
    successful = 0
    failed = 0
    
    for symbol in WATCHLIST_STOCKS:
        try:
            print(f"   🔍 Analyzing {symbol}...")
            # Use the real client to get technical data
            tech_data = get_technicals_for_symbol(symbol, client)
            
            if tech_data and not tech_data.get('error'):
                watchlist_stocks[symbol] = tech_data
                successful += 1
                price = tech_data.get('market_price', 'N/A')
                print(f"      ✅ {symbol}: ${price}")
            else:
                watchlist_stocks[symbol] = {"error": "Failed to get technical data"}
                failed += 1
                print(f"      ❌ {symbol}: Failed")
                
        except Exception as e:
            watchlist_stocks[symbol] = {"error": str(e)}
            failed += 1
            print(f"      ❌ {symbol}: Error - {e}")
    
    # Create the watchlist data structure
    watchlist_data = {
        "watchlist_stocks": watchlist_stocks,
        "summary": {
            "total_watchlist_analyzed": len(WATCHLIST_STOCKS),
            "successful_analyses": successful,
            "failed_analyses": failed,
            "watchlist_signals": {}
        }
    }
    
    # Add metadata
    full_data = {
        "generated_at": datetime.now().isoformat(),
        "config_path": "config/settings.py",
        "storage_reason": "fresh_generation",
        "client_type": client_type,
        **watchlist_data
    }
    
    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("data/stock_watchlist")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"watchlist_fresh_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        json.dump(full_data, f, indent=2)
    
    print(f"💾 Fresh watchlist data saved to: {output_file}")
    
    # Show sample prices
    print(f"\n📈 SAMPLE PRICES FROM FRESH DATA:")
    watchlist_stocks = full_data.get("watchlist_stocks", {})
    for symbol in ["AAL", "AMD", "UBER"][:3]:  # Show first 3
        if symbol in watchlist_stocks:
            stock_data = watchlist_stocks[symbol]
            if "error" not in stock_data:
                price = stock_data.get("market_price", "N/A")
                print(f"   {symbol}: ${price}")
            else:
                print(f"   {symbol}: Error - {stock_data['error']}")
    
    return output_file

if __name__ == "__main__":
    try:
        output_file = generate_fresh_watchlist()
        print(f"\n✅ Fresh watchlist data generated successfully!")
        print(f"📂 File: {output_file}")
    except Exception as e:
        print(f"❌ Error generating fresh watchlist data: {e}")
        sys.exit(1)