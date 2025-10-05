#!/usr/bin/env python3
"""Test the data loading logic of put selection engine without API calls."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from strategies.put_selection import PutSelectionEngine
from utils.logging import setup_logging

def test_data_loading():
    """Test the data loading functionality without API calls."""
    setup_logging('INFO')
    
    print("🔍 Testing Put Selection Data Loading")
    print("=" * 50)
    
    # Create engine (with mock client)
    engine = PutSelectionEngine(client=None, data_dir="data", max_total_allocation_pct=20.0)
    
    # Test loading account allocations
    print("\n📊 Testing account allocation loading...")
    allocations = engine._load_account_allocations()
    
    if allocations:
        print(f"✅ Loaded allocations for {len(allocations)} symbols:")
        for symbol, data in list(allocations.items())[:5]:  # Show first 5
            total_alloc = data.get('total_allocation_pct', '0')
            stock_alloc = data.get('stock_allocation_pct', '0')  
            puts_alloc = data.get('put_collateral_pct', '0')
            print(f"   {symbol}: {total_alloc}% total ({stock_alloc}% stock + {puts_alloc}% puts)")
        
        if len(allocations) > 5:
            print(f"   ... and {len(allocations) - 5} more symbols")
    else:
        print("❌ No account allocations found")
        print("   Make sure data/account/account_snapshot.json exists")
    
    # Test loading wheel rankings
    print("\n🎯 Testing wheel rankings loading...")
    rankings = engine._load_latest_wheel_rankings()
    
    if rankings:
        print(f"✅ Loaded rankings for {len(rankings)} symbols:")
        
        # Count by grade
        grade_counts = {}
        for symbol, data in rankings.items():
            grade = data.get('overall_grade', 'UNKNOWN')
            grade_counts[grade] = grade_counts.get(grade, 0) + 1
        
        for grade, count in sorted(grade_counts.items()):
            print(f"   {grade}: {count} symbols")
        
        # Show a few examples
        print(f"\n   Sample rankings:")
        for symbol, data in list(rankings.items())[:3]:
            grade = data.get('overall_grade', 'UNKNOWN')
            score = data.get('final_score', 'N/A')
            print(f"   {symbol}: {grade} (score: {score})")
    else:
        print("❌ No wheel rankings found")
        print("   Make sure data/stock_ranking/wheel_rankings_*.json exists")
    
    # Test eligible symbols logic
    print("\n🎲 Testing eligible symbols selection...")
    eligible = engine._get_eligible_symbols()
    
    if eligible:
        print(f"✅ Found {len(eligible)} eligible symbols for put analysis:")
        for symbol, grade, current_alloc in eligible[:10]:  # Show first 10
            remaining = engine.max_total_allocation_pct - current_alloc
            print(f"   {symbol} ({grade}): {current_alloc:.1f}% allocated, {remaining:.1f}% remaining")
        
        if len(eligible) > 10:
            print(f"   ... and {len(eligible) - 10} more eligible symbols")
        
        # Show criteria that would be applied
        print(f"\n⚙️  Grade-based criteria preview:")
        for grade, criteria in engine.grade_criteria.items():
            count = len([x for x in eligible if x[1] == grade])
            if count > 0:
                print(f"   {grade} ({count} symbols): "
                      f"≥{criteria['min_annualized_return']:.0f}% return, "
                      f"≥{criteria['min_downside_protection']:.0f}% protection, "
                      f"≤{criteria['max_assignment_prob']:.0f}% assignment risk")
    else:
        print("❌ No eligible symbols found")
        reasons = []
        if not allocations:
            reasons.append("No account allocations data")
        if not rankings:
            reasons.append("No wheel rankings data") 
        if allocations and rankings:
            # Check if all symbols have >20% allocation
            high_alloc_count = 0
            for symbol in rankings.keys():
                alloc = float(allocations.get(symbol, {}).get('total_allocation_pct', '0'))
                if alloc >= engine.max_total_allocation_pct:
                    high_alloc_count += 1
            if high_alloc_count == len(rankings):
                reasons.append("All ranked symbols have ≥20% allocation")
        
        if reasons:
            print(f"   Possible reasons: {', '.join(reasons)}")
    
    print(f"\n✅ Data loading test complete!")
    return len(eligible) > 0

def main():
    """Run the data loading test."""
    success = test_data_loading()
    
    if success:
        print("\n🎉 Put selection engine is ready!")
        print("   - Account allocation data loaded successfully")  
        print("   - Wheel rankings data loaded successfully")
        print("   - Eligible symbols identified for analysis")
        print("   - Grade-based criteria configured")
        print("\n   Next step: Run with real API client to get put opportunities")
    else:
        print("\n⚠️  Put selection engine needs data setup:")
        print("   1. Run main.py to generate account_snapshot.json")
        print("   2. Run scripts/rank_wheel_candidates.py to generate wheel rankings")
        print("   3. Then test the put selection engine")

if __name__ == "__main__":
    main()