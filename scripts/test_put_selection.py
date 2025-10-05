#!/usr/bin/env python3
"""Test script for data-driven cash secured put selection."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.client import RealBrokerClient
from strategies.put_selection import find_cash_secured_put_opportunities
from utils.logging import setup_logging

def main():
    """Test the new put selection engine with account and ranking data."""
    setup_logging('INFO')
    
    print("🔍 Testing Data-Driven Put Selection Engine")
    print("=" * 60)
    
    # Initialize client
    try:
        client = RealBrokerClient()
        print("✅ Schwab client initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        return
    
    # Get account snapshot
    print("\n📊 Getting account snapshot...")
    try:
        snapshot = client.get_account_snapshot()
        total_value = snapshot.official_liquidation_value or snapshot.cash
        print(f"✅ Account loaded: ${total_value:,.2f} total value")
    except Exception as e:
        print(f"❌ Failed to get account snapshot: {e}")
        return
    
    # Test put selection with account data and wheel rankings
    print("\n🎯 Analyzing cash secured put opportunities...")
    print("   Using account allocations and wheel rankings for intelligent selection")
    
    try:
        put_opportunities = find_cash_secured_put_opportunities(
            client, 
            snapshot,
            data_dir="data",
            max_total_allocation_pct=20.0  # Only consider stocks with <20% allocation
        )
        
        if not put_opportunities:
            print("ℹ️  No put opportunities found")
            print("   This could mean:")
            print("   - No stocks have <20% allocation")
            print("   - No wheel rankings data available") 
            print("   - All stocks failed grade-based criteria")
            return
        
        print(f"📈 Found put opportunities for {len(put_opportunities)} symbols:")
        print()
        
        # Sort by grade and score for display
        sorted_opps = sorted(put_opportunities.items(), 
                           key=lambda x: (
                               {'EXCELLENT': 0, 'GOOD': 1, 'FAIR': 2, 'POOR': 3}.get(x[1]['grade'], 99),
                               -max([p['attractiveness_score'] for p in x[1]['recommended_puts']], default=0)
                           ))
        
        for symbol, data in sorted_opps:
            grade = data['grade']
            current_price = data['current_price']
            current_alloc = data['current_allocation_pct']
            remaining_alloc = data['remaining_allocation_pct']
            min_score = data['min_score_applied']
            
            # Grade emoji
            grade_emoji = {
                'EXCELLENT': '⭐',
                'GOOD': '✅', 
                'FAIR': '⚠️',
                'POOR': '�'
            }.get(grade, '❓')
            
            print(f"   {grade_emoji} {symbol} ({grade}): ${current_price:.2f}")
            print(f"      Current allocation: {current_alloc:.1f}% | Available: {remaining_alloc:.1f}%")
            print(f"      Min score applied: {min_score:.0f}")
            
            # Show top 2-3 put recommendations
            for i, put in enumerate(data['recommended_puts'][:3], 1):
                strike = put['strike_price']
                premium = put['premium']
                dte = put['days_to_expiry']
                annual_return = put['annualized_return_pct']
                protection = put['downside_protection_pct']
                score = put['attractiveness_score']
                max_contracts = put['max_contracts']
                total_income = put['total_premium_income']
                
                print(f"         {i}. ${strike:.0f} strike, {dte}d: "
                      f"${premium:.2f} premium ({annual_return:.1f}% annual, "
                      f"{protection:.1f}% protection)")
                print(f"            Max {max_contracts} contracts = ${total_income:,.0f} income "
                      f"[Score: {score:.0f}]")
            
            print()
        
        # Summary statistics
        total_puts = sum(len(data['recommended_puts']) for data in put_opportunities.values())
        excellent_count = len([d for d in put_opportunities.values() if d['grade'] == 'EXCELLENT'])
        good_count = len([d for d in put_opportunities.values() if d['grade'] == 'GOOD'])
        fair_count = len([d for d in put_opportunities.values() if d['grade'] == 'FAIR'])
        poor_count = len([d for d in put_opportunities.values() if d['grade'] == 'POOR'])
        
        print("📊 SUMMARY:")
        print(f"   Total opportunities: {total_puts} puts across {len(put_opportunities)} symbols")
        print(f"   By grade: {excellent_count} EXCELLENT, {good_count} GOOD, {fair_count} FAIR, {poor_count} POOR")
        
        # Show criteria being applied
        if put_opportunities:
            sample_criteria = list(put_opportunities.values())[0]['criteria_applied']
            print(f"\n⚙️  EXAMPLE CRITERIA (for first stock's grade):")
            print(f"   Min annualized return: {sample_criteria['min_annualized_return']:.1f}%")
            print(f"   Min downside protection: {sample_criteria['min_downside_protection']:.1f}%")
            print(f"   Max assignment probability: {sample_criteria['max_assignment_prob']:.1f}%")
            print(f"   Preferred DTE range: {sample_criteria['preferred_dte_range']}")
            print(f"   Aggressiveness multiplier: {sample_criteria['aggressiveness_multiplier']:.1f}x")
        
    except Exception as e:
        print(f"❌ Error analyzing put opportunities: {e}")
        import traceback
        traceback.print_exc()
        return

if __name__ == "__main__":
    main()