"""Test script to verify real-time market data changes."""

import time
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.client import RealBrokerClient
from utils.config_schwab import SchwabConfig
from core.orchestrator import run_once


def test_market_data_changes(samples: int = 3, interval: int = 5) -> bool:
    """
    Test that market data actually changes over time.
    
    Args:
        samples: Number of data samples to collect
        interval: Seconds between samples
    
    Returns:
        True if market data is changing, False otherwise
    """
    print(f"📊 Testing market data changes over {samples} samples with {interval}s intervals...")
    
    # Initialize client
    config = SchwabConfig.from_env()
    config.app_key = "ER0kVS2P0U9WMMlRRt7Mw4ELCmVRwTB5"
    config.app_secret = "3mJejG1MBpISgcjj"
    
    client = RealBrokerClient(
        app_key=config.app_key,
        app_secret=config.app_secret,
        redirect_uri=config.redirect_uri,
        token_path=config.token_path
    )
    
    # Collect samples
    samples_data: List[Dict[str, Any]] = []
    
    for i in range(samples):
        print(f"  📈 Collecting sample {i + 1}/{samples}...")
        
        result = run_once(client, include_technicals=False)
        snapshot = result['snapshot']
        
        # Extract key data points that should change with market movement
        sample_data = {
            'timestamp': snapshot.generated_at,
            'total_value': result['total_account_value'],
            'stock_prices': {stock.symbol: stock.market_price for stock in snapshot.stocks},
            'option_prices': {option.contract_symbol: option.market_price for option in snapshot.options}
        }
        
        samples_data.append(sample_data)
        
        if i < samples - 1:  # Don't sleep after the last sample
            print(f"  ⏳ Waiting {interval}s for next sample...")
            time.sleep(interval)
    
    # Analyze changes
    print("\n🔍 Analyzing data changes...")
    
    changes_detected = []
    
    # Check if timestamps are different
    timestamps = [sample['timestamp'] for sample in samples_data]
    unique_timestamps = set(timestamps)
    
    if len(unique_timestamps) > 1:
        changes_detected.append("✅ Timestamps are changing (fresh data)")
        time_range = max(timestamps) - min(timestamps)
        print(f"   Time range: {time_range.total_seconds():.1f} seconds")
    else:
        print("❌ Timestamps are identical (stale data)")
    
    # Check if account values are changing
    values = [sample['total_value'] for sample in samples_data]
    unique_values = set(values)
    
    if len(unique_values) > 1:
        changes_detected.append("✅ Account values are changing")
        min_val, max_val = min(values), max(values)
        value_range_pct = (max_val - min_val) / min_val * 100
        print(f"   Value range: ${min_val:,.2f} - ${max_val:,.2f} ({value_range_pct:.3f}% variation)")
    else:
        print(f"❌ Account values are identical: ${values[0]:,.2f}")
    
    # Check if individual stock prices are changing
    stock_symbols = set()
    for sample in samples_data:
        stock_symbols.update(sample['stock_prices'].keys())
    
    changing_stocks = 0
    for symbol in stock_symbols:
        prices = [sample['stock_prices'].get(symbol) for sample in samples_data if sample['stock_prices'].get(symbol) is not None]
        
        if len(set(prices)) > 1:
            changing_stocks += 1
            min_price, max_price = min(prices), max(prices)
            price_range_pct = (max_price - min_price) / min_price * 100
            print(f"   {symbol}: ${min_price:.2f} - ${max_price:.2f} ({price_range_pct:.3f}% variation)")
    
    if changing_stocks > 0:
        changes_detected.append(f"✅ {changing_stocks} stock prices changing")
    else:
        print("❌ No stock prices are changing")
    
    # Check if option prices are changing
    option_symbols = set()
    for sample in samples_data:
        option_symbols.update(sample['option_prices'].keys())
    
    changing_options = 0
    for symbol in option_symbols:
        prices = [sample['option_prices'].get(symbol) for sample in samples_data if sample['option_prices'].get(symbol) is not None]
        
        if len(set(prices)) > 1:
            changing_options += 1
            min_price, max_price = min(prices), max(prices)
            if min_price > 0:
                price_range_pct = (max_price - min_price) / min_price * 100
                print(f"   {symbol}: ${min_price:.2f} - ${max_price:.2f} ({price_range_pct:.3f}% variation)")
    
    if changing_options > 0:
        changes_detected.append(f"✅ {changing_options} option prices changing")
    else:
        print("❌ No option prices are changing")
    
    # Summary
    print(f"\n📋 SUMMARY:")
    for change in changes_detected:
        print(f"  {change}")
    
    # Determine if we're getting real-time data
    is_real_time = len(changes_detected) >= 2  # At least timestamps + one price type changing
    
    if is_real_time:
        print("🎉 CONFIRMED: Real-time market data is being retrieved!")
    else:
        print("⚠️  WARNING: Market data may be stale or markets may be closed")
        
        # Check if markets might be closed
        now = datetime.now()
        # Simple check for weekends
        if now.weekday() >= 5:  # Saturday or Sunday
            print("   Note: Markets are likely closed (weekend)")
        else:
            # Check for market hours (rough estimate - 9:30 AM to 4:00 PM ET)
            # This is a simplified check and doesn't account for holidays
            market_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
            market_end = now.replace(hour=16, minute=0, second=0, microsecond=0)
            
            if now < market_start or now > market_end:
                print(f"   Note: Markets may be closed (current time: {now.strftime('%H:%M:%S')})")
    
    return is_real_time


if __name__ == "__main__":
    # Test with 3 samples, 10 seconds apart during market hours
    # Or 3 samples, 5 seconds apart for after-hours testing
    
    # Check if it's likely market hours
    now = datetime.now()
    is_likely_market_hours = (
        now.weekday() < 5 and  # Monday-Friday
        9 <= now.hour < 16      # Rough market hours
    )
    
    if is_likely_market_hours:
        # During market hours, expect more frequent changes
        success = test_market_data_changes(samples=3, interval=10)
    else:
        # After hours, less frequent changes expected
        success = test_market_data_changes(samples=3, interval=5)
    
    sys.exit(0 if success else 1)