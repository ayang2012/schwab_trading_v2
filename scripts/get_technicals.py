#!/usr/bin/env python3
"""
Quick Technical Analysis Lookup Tool

Usage:
    python scripts/get_technicals.py AAPL
    python scripts/get_technicals.py "AAPL  241220C00150000"
    python scripts/get_technicals.py AAL TSLA MSFT

A simple command-line tool to get technical analysis for any stock or option symbol.
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from analysis.technicals import get_technicals_for_symbol
import json
import argparse


def format_stock_output(data):
    """Format stock technical analysis for readable output."""
    print(f"\n📊 {data['symbol']} - Stock Analysis")
    print("=" * 50)
    print(f"Current Price: ${data.get('market_price', 'N/A')}")
    print(f"RSI (14): {data.get('rsi', 'N/A')}")
    print(f"SMA 20: ${data.get('sma_20', 'N/A')}")
    print(f"SMA 50: ${data.get('sma_50', 'N/A')}")
    print(f"MACD: {data.get('macd', 'N/A')}")
    
    bb = data.get('bollinger_bands', {})
    if bb:
        print(f"Bollinger Bands: ${bb.get('lower', 'N/A')} - ${bb.get('upper', 'N/A')}")
    
    price_range = data.get('price_range', {})
    if price_range:
        print(f"Day Range: ${price_range.get('day_low', 'N/A')} - ${price_range.get('day_high', 'N/A')}")
        print(f"52W Range: ${price_range.get('52_week_low', 'N/A')} - ${price_range.get('52_week_high', 'N/A')}")
    
    print(f"Volume (10d avg): {data.get('volume_avg_10', 'N/A'):,}")
    print(f"Price Change: {data.get('price_change_pct', 'N/A')}%")
    
    signals = data.get('signals', [])
    if signals:
        print(f"Signals: {', '.join(signals)}")


def format_option_output(data):
    """Format option technical analysis for readable output."""
    print(f"\n📈 {data['symbol']} - Option Analysis")
    print("=" * 50)
    print(f"Underlying: {data.get('underlying', 'N/A')} @ ${data.get('underlying_price', 'N/A')}")
    print(f"Strike: ${data.get('strike', 'N/A')} {data.get('option_type', 'N/A')}")
    print(f"Expiry: {data.get('expiry', 'N/A')} ({data.get('days_to_expiration', 'N/A')} days)")
    print(f"Premium: ${data.get('premium', 'N/A')} (Bid: ${data.get('bid', 'N/A')}, Ask: ${data.get('ask', 'N/A')})")
    
    print(f"\nGreeks:")
    print(f"  Delta: {data.get('delta', 'N/A')}")
    print(f"  Gamma: {data.get('gamma', 'N/A')}")
    print(f"  Theta: {data.get('theta', 'N/A')}")
    print(f"  Vega: {data.get('vega', 'N/A')}")
    print(f"  Rho: {data.get('rho', 'N/A')}")
    
    print(f"\nRisk Metrics:")
    print(f"  Implied Vol: {data.get('implied_volatility', 'N/A')}")
    print(f"  Intrinsic Value: ${data.get('intrinsic_value', 'N/A')}")
    print(f"  Time Value: ${data.get('time_value', 'N/A')}")
    print(f"  Moneyness: {data.get('moneyness', 'N/A')}")
    
    print(f"\nMarket Data:")
    print(f"  Volume: {data.get('volume', 'N/A'):,}")
    print(f"  Open Interest: {data.get('open_interest', 'N/A'):,}")
    print(f"  Liquidity: {data.get('liquidity', 'N/A')}")
    
    signals = data.get('signals', [])
    if signals:
        print(f"  Signals: {', '.join(signals)}")


def analyze_symbol(symbol):
    """Analyze a single symbol and display results."""
    try:
        print(f"🔍 Analyzing {symbol}...")
        data = get_technicals_for_symbol(symbol)
        
        if 'error' in data:
            print(f"❌ Error analyzing {symbol}: {data['error']}")
            return False
        
        if data.get('type') == 'stock':
            format_stock_output(data)
        elif data.get('type') == 'option':
            format_option_output(data)
        else:
            print(f"📋 Raw data for {symbol}:")
            print(json.dumps(data, indent=2, default=str))
        
        return True
        
    except Exception as e:
        print(f"❌ Unexpected error analyzing {symbol}: {e}")
        return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Get technical analysis for stock or option symbols',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s AAPL                          # Stock analysis
  %(prog)s "AAPL  241220C00150000"       # Option analysis (note the quotes)
  %(prog)s AAPL MSFT TSLA                # Multiple stocks
  %(prog)s --json AAPL                   # Raw JSON output
  %(prog)s --compact AAPL MSFT           # Compact format
        """
    )
    
    parser.add_argument('symbols', nargs='+', help='Stock tickers or option symbols to analyze')
    parser.add_argument('--json', action='store_true', help='Output raw JSON instead of formatted text')
    parser.add_argument('--compact', action='store_true', help='Use compact output format')
    
    args = parser.parse_args()
    
    if not args.symbols:
        parser.print_help()
        return
    
    print("🚀 Technical Analysis Lookup Tool")
    print(f"Analyzing {len(args.symbols)} symbol(s)...")
    
    success_count = 0
    
    for symbol in args.symbols:
        symbol = symbol.strip()
        if not symbol:
            continue
            
        try:
            data = get_technicals_for_symbol(symbol)
            
            if args.json:
                print(json.dumps(data, indent=2, default=str))
            elif args.compact:
                symbol_type = data.get('type', 'unknown')
                signals = data.get('signals', [])
                if symbol_type == 'stock':
                    rsi = data.get('rsi', 'N/A')
                    price = data.get('market_price', 'N/A')
                    print(f"{symbol:8} | Stock | ${price:>8} | RSI: {rsi:>5} | {', '.join(signals[:2])}")
                elif symbol_type == 'option':
                    premium = data.get('premium', 'N/A')
                    delta = data.get('delta', 'N/A')
                    dte = data.get('days_to_expiration', 'N/A')
                    print(f"{symbol:20} | Option | ${premium:>6} | Δ: {delta:>6} | {dte:>3}d | {', '.join(signals[:2])}")
            else:
                if analyze_symbol(symbol):
                    success_count += 1
                    
        except Exception as e:
            print(f"❌ Error processing {symbol}: {e}")
    
    if not args.json and not args.compact:
        print(f"\n✅ Analysis complete! Successfully analyzed {success_count}/{len(args.symbols)} symbols.")
        print(f"💡 Tip: Use --json for raw data or --compact for quick overview")


if __name__ == "__main__":
    main()