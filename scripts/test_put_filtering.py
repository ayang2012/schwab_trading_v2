#!/usr/bin/env python3
"""Test the complete put selection filtering process with detailed breakdown."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from strategies.put_selection import PutSelectionEngine
from utils.logging import setup_logging

def test_complete_filtering():
    """Test all filtering stages of put selection."""
    setup_logging('INFO')
    
    print("🔍 Complete Put Selection Filtering Test")
    print("=" * 60)
    
    # Create engine
    engine = PutSelectionEngine(client=None, data_dir="data", max_total_allocation_pct=20.0)
    
    # Load all data sources
    allocations = engine._load_account_allocations()
    rankings = engine._load_latest_wheel_rankings()
    technical_data = engine._load_technical_data()
    current_options = engine._load_current_option_positions()
    
    print(f"📊 Data Sources Loaded:")
    print(f"   • Account allocations: {len(allocations)} symbols")
    print(f"   • Wheel rankings: {len(rankings)} symbols")
    print(f"   • Technical data: {len(technical_data)} symbols") 
    print(f"   • Current options: {len(current_options)} symbols")
    
    print(f"\n🎯 Filtering Process for Wheel Ranking Symbols:")
    print("-" * 50)
    
    total_candidates = 0
    passed_stages = {
        'initial': 0,
        'option_filter': 0,
        'allocation_filter': 0,
        'grade_filter': 0,
        'technical_filter': 0,
        'final_eligible': 0
    }
    
    for symbol, ranking_data in rankings.items():
        total_candidates += 1
        grade = ranking_data.get('overall_grade', 'UNKNOWN')
        
        print(f"\n{symbol} ({grade}):")
        
        passed_stages['initial'] += 1
        
        # Stage 1: Option position filter
        if symbol in current_options:
            positions = current_options[symbol]
            position_summary = []
            for pos in positions:
                qty = pos.get('qty', 0)
                put_call = pos.get('put_call', 'UNKNOWN')
                strike = pos.get('strike', 'N/A')
                expiry = pos.get('expiry', 'N/A')[:10] if pos.get('expiry') else 'N/A'
                position_summary.append(f"{qty} {put_call} ${strike}")
            print(f"   ❌ OPTION CONFLICT: Has {', '.join(position_summary)}")
            continue
        
        print(f"   ✅ Option Check: No existing positions")
        passed_stages['option_filter'] += 1
        
        # Stage 2: Allocation filter
        current_allocation = float(allocations.get(symbol, {}).get('total_allocation_pct', '0'))
        if current_allocation >= engine.max_total_allocation_pct:
            print(f"   ❌ ALLOCATION: {current_allocation:.1f}% >= {engine.max_total_allocation_pct}%")
            continue
        
        print(f"   ✅ Allocation Check: {current_allocation:.1f}% < {engine.max_total_allocation_pct}%")
        passed_stages['allocation_filter'] += 1
        
        # Stage 3: Grade filter
        if grade not in engine.grade_criteria:
            print(f"   ❌ GRADE: Unknown grade '{grade}'")
            continue
        
        print(f"   ✅ Grade Check: {grade} grade recognized")
        passed_stages['grade_filter'] += 1
        
        # Stage 4: Technical filter
        symbol_technical = technical_data.get(symbol, {})
        if not engine._validate_technical_criteria(symbol, grade, symbol_technical):
            print(f"   ❌ TECHNICAL: Failed {grade} grade criteria")
            if symbol_technical:
                indicators = symbol_technical.get('technical_indicators', {})
                signals = symbol_technical.get('signals', [])
                rsi = indicators.get('rsi', 'N/A')
                volume_ratio = indicators.get('volume_ratio', 'N/A')
                print(f"      RSI: {rsi}, Volume: {volume_ratio}")
                print(f"      Signals: {', '.join(signals[:2])}...")
            else:
                print(f"      No technical data available")
            continue
        
        print(f"   ✅ Technical Check: Meets {grade} criteria")
        if symbol_technical:
            indicators = symbol_technical.get('technical_indicators', {})
            rsi = indicators.get('rsi', 'N/A')
            volume_ratio = indicators.get('volume_ratio', 'N/A')
            print(f"      RSI: {rsi}, Volume: {volume_ratio}")
        passed_stages['technical_filter'] += 1
        
        print(f"   🎉 ELIGIBLE: Ready for put analysis")
        passed_stages['final_eligible'] += 1
    
    print(f"\n📈 Filtering Summary:")
    print("-" * 30)
    print(f"Initial candidates:     {passed_stages['initial']:2d}")
    print(f"After option filter:    {passed_stages['option_filter']:2d}")
    print(f"After allocation filter:{passed_stages['allocation_filter']:2d}")
    print(f"After grade filter:     {passed_stages['grade_filter']:2d}")
    print(f"After technical filter: {passed_stages['technical_filter']:2d}")
    print(f"Final eligible:         {passed_stages['final_eligible']:2d}")
    
    filter_rate = (1 - passed_stages['final_eligible'] / passed_stages['initial']) * 100
    print(f"\nFilter efficiency: {filter_rate:.1f}% filtered out")
    
    # Show criteria for eligible symbols
    if passed_stages['final_eligible'] > 0:
        print(f"\n⚙️  Applied Criteria for Eligible Symbols:")
        eligible = engine._get_eligible_symbols()
        for symbol, grade, allocation in eligible:
            criteria = engine.grade_criteria[grade]
            print(f"{symbol} ({grade}): ≥{criteria['min_annualized_return']:.0f}% return, "
                  f"≥{criteria['min_downside_protection']:.1f}% protection, "
                  f"≤{criteria['max_assignment_prob']:.0f}% assignment risk")

def main():
    """Run the complete filtering test."""
    test_complete_filtering()
    print(f"\n✅ Complete filtering test finished!")

if __name__ == "__main__":
    main()