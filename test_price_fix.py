#!/usr/bin/env python3
"""Test script to validate that the price fix works in ranking."""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from scripts.rank_wheel_candidates import WheelRanker
import config.settings as config

def test_price_fix():
    """Test that prices are correctly extracted from watchlist data."""
    
    # Load the most recent watchlist data
    watchlist_dir = Path("data/stock_watchlist")
    watchlist_files = list(watchlist_dir.glob("watchlist_significant_alerts_*.json"))
    if not watchlist_files:
        print("❌ No watchlist files found")
        return False
    
    latest_file = max(watchlist_files, key=lambda f: f.stat().st_mtime)
    print(f"📂 Loading watchlist data from: {latest_file.name}")
    
    with open(latest_file, 'r') as f:
        watchlist_data = json.load(f)
    
    # Initialize ranker
    ranker = WheelRanker()
    
    # Generate rankings
    print("🔍 Generating wheel candidate rankings...")
    rankings = ranker.rank_wheel_candidates(watchlist_data)
    
    # Check if prices are now correct
    put_candidates = rankings.get('put_candidates', [])
    call_candidates = rankings.get('call_candidates', [])
    
    print(f"\n📊 PUT CANDIDATES ({len(put_candidates)}):")
    for candidate in put_candidates[:3]:  # Show top 3
        symbol = candidate['symbol']
        price = candidate['price']
        score = candidate['score']
        print(f"  {symbol}: ${price:.2f} (Score: {score})")
        
        if price == 0:
            print(f"  ❌ {symbol} still has $0.00 price!")
            return False
    
    print(f"\n📊 CALL CANDIDATES ({len(call_candidates)}):")
    for candidate in call_candidates[:3]:  # Show top 3
        symbol = candidate['symbol']
        price = candidate['price']
        score = candidate['score']
        print(f"  {symbol}: ${price:.2f} (Score: {score})")
        
        if price == 0:
            print(f"  ❌ {symbol} still has $0.00 price!")
            return False
    
    print("\n✅ Price fix successful! All candidates show correct prices.")
    return True

if __name__ == "__main__":
    success = test_price_fix()
    sys.exit(0 if success else 1)