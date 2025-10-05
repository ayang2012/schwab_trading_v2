#!/usr/bin/env python3
"""
Weekly Put Selection Engine - Live Run
Generates comprehensive put recommendations with detailed analysis and reasoning.
"""

import sys
from pathlib import Path
from datetime import datetime
import json
from decimal import Decimal

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from strategies.put_selection import PutSelectionEngine
from core.models import AccountSnapshot
from api.client import RealBrokerClient
from api.sim_client import SimBrokerClient
from utils.config_schwab import SchwabConfig
from utils.logging import setup_logging

def calculate_composite_score(put):
    """Calculate composite score for ranking puts"""
    scores = {}
    
    # 1. Weekly Return Score (40% weight)
    weekly_return = put['annualized_return_pct'] / 52
    if weekly_return >= 2.0:
        scores['return'] = 10
    elif weekly_return >= 1.5:
        scores['return'] = 8
    elif weekly_return >= 1.0:
        scores['return'] = 6
    elif weekly_return >= 0.5:
        scores['return'] = 4
    else:
        scores['return'] = 2
    
    # 2. Quality Score (25% weight)
    grade_scores = {'EXCELLENT': 10, 'GOOD': 7, 'FAIR': 4, 'POOR': 1}
    scores['quality'] = grade_scores.get(put['grade'], 1)
    
    # 3. Assignment Likelihood (20% weight)
    oi = put['open_interest']
    if oi >= 500:
        scores['assignment'] = 10
    elif oi >= 100:
        scores['assignment'] = 8
    elif oi >= 50:
        scores['assignment'] = 6
    elif oi >= 25:
        scores['assignment'] = 4
    else:
        scores['assignment'] = 2
    
    # 4. Liquidity Score (10% weight)
    spread = put['bid_ask_spread_pct']
    if spread <= 3:
        scores['liquidity'] = 10
    elif spread <= 6:
        scores['liquidity'] = 8
    elif spread <= 10:
        scores['liquidity'] = 6
    elif spread <= 15:
        scores['liquidity'] = 4
    else:
        scores['liquidity'] = 2
    
    # 5. Risk Score (5% weight)
    protection = put['downside_protection_pct']
    if protection >= 10:
        scores['risk'] = 10
    elif protection >= 5:
        scores['risk'] = 8
    elif protection >= 2:
        scores['risk'] = 6
    else:
        scores['risk'] = 4
    
    # Calculate weighted composite score
    weights = {
        'return': 0.40,
        'quality': 0.25, 
        'assignment': 0.20,
        'liquidity': 0.10,
        'risk': 0.05
    }
    
    composite = sum(scores[factor] * weights[factor] for factor in scores)
    return composite, scores

def generate_final_selections(raw_data, timestamp):
    """Extract top choice for each stock based on composite scoring"""
    final_recommendations = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "strategy": "weekly_cash_secured_puts_final_selections",
            "account_value": raw_data['metadata']['account_value'],
            "available_cash": raw_data['metadata']['available_cash'],
            "selection_criteria": "Top composite score per symbol",
            "scoring_weights": {
                "return_potential": "40%",
                "underlying_quality": "25%", 
                "assignment_likelihood": "20%",
                "liquidity": "10%",
                "risk_management": "5%"
            },
            "source_file": f"put_recommendations_{timestamp}.json"
        },
        "final_selections": {}
    }
    
    if 'put_recommendations' in raw_data:
        for symbol, symbol_data in raw_data['put_recommendations'].items():
            recommended_puts = symbol_data.get('recommended_puts', [])
            
            if not recommended_puts:
                continue
                
            # Calculate scores for all puts for this symbol
            scored_puts = []
            for put in recommended_puts:
                composite, breakdown = calculate_composite_score(put)
                put_with_score = put.copy()
                put_with_score['composite_score'] = round(composite, 2)
                put_with_score['score_breakdown'] = breakdown
                put_with_score['weekly_return_pct'] = round(put['annualized_return_pct'] / 52, 2)
                scored_puts.append(put_with_score)
            
            # Sort by composite score and take the top one
            scored_puts.sort(key=lambda x: x['composite_score'], reverse=True)
            top_choice = scored_puts[0]
            
            # Add selection reasoning
            final_recommendations['final_selections'][symbol] = {
                "symbol": symbol,
                "grade": symbol_data['grade'],
                "current_price": symbol_data['current_price'],
                "top_put_choice": top_choice,
                "selection_reasoning": {
                    "composite_score": top_choice['composite_score'],
                    "weekly_return_pct": top_choice['weekly_return_pct'],
                    "why_selected": f"Highest composite score ({top_choice['composite_score']}/10) among {len(recommended_puts)} options",
                    "key_strengths": []
                },
                "alternatives_count": len(recommended_puts) - 1,
                "analysis_timestamp": symbol_data['analysis_timestamp']
            }
            
            # Add key strengths based on scores
            scores = top_choice['score_breakdown']
            strengths = []
            if scores['return'] >= 8:
                strengths.append(f"Excellent return potential ({top_choice['weekly_return_pct']}% weekly)")
            elif scores['return'] >= 6:
                strengths.append(f"Good return potential ({top_choice['weekly_return_pct']}% weekly)")
                
            if scores['quality'] == 10:
                strengths.append("EXCELLENT underlying quality")
            elif scores['quality'] >= 7:
                strengths.append("GOOD underlying quality")
                
            if scores['assignment'] >= 8:
                strengths.append(f"High assignment likelihood (OI: {top_choice['open_interest']:,})")
            elif scores['assignment'] >= 6:
                strengths.append(f"Good assignment likelihood (OI: {top_choice['open_interest']:,})")
                
            if scores['liquidity'] >= 8:
                strengths.append(f"Excellent liquidity ({top_choice['bid_ask_spread_pct']}% spread)")
            elif scores['liquidity'] >= 6:
                strengths.append(f"Good liquidity ({top_choice['bid_ask_spread_pct']}% spread)")
                
            final_recommendations['final_selections'][symbol]['selection_reasoning']['key_strengths'] = strengths
    
    return final_recommendations

def load_account_snapshot() -> AccountSnapshot:
    """Load the current account snapshot."""
    try:
        snapshot_file = Path("data/account/account_snapshot.json")
        with open(snapshot_file, 'r') as f:
            data = json.load(f)
        
        # Create AccountSnapshot from the data
        return AccountSnapshot(
            generated_at=datetime.now(),
            cash=Decimal(str(data.get('cash', '0'))),
            buying_power=Decimal(str(data.get('buying_power', '0'))),
            stocks=[],  # We don't need positions for put selection
            options=[],
            mutual_funds=[],
            official_liquidation_value=Decimal(str(data.get('total_account_value', '100000')))
        )
    except Exception as e:
        print(f"Error loading account snapshot: {e}")
        return AccountSnapshot(
            generated_at=datetime.now(),
            cash=Decimal('10000'),
            buying_power=Decimal('10000'),
            stocks=[],
            options=[],
            mutual_funds=[],
            official_liquidation_value=Decimal('100000')
        )

def generate_selection_reasoning(symbol: str, grade: str, technical_data: dict, 
                               current_allocation: float, criteria: dict) -> dict:
    """Generate detailed reasoning for why a symbol was selected."""
    reasoning = {
        "fundamental_analysis": {
            "wheel_grade": grade,
            "grade_description": {
                "EXCELLENT": "Strong fundamentals, stable business, low volatility risk",
                "GOOD": "Solid fundamentals, moderate business stability", 
                "FAIR": "Mixed fundamentals, higher volatility potential",
                "POOR": "Weak fundamentals, significant risk factors"
            }.get(grade, "Unknown grade"),
            "grade_confidence": "High" if grade in ["EXCELLENT", "GOOD"] else "Medium" if grade == "FAIR" else "Low"
        },
        "technical_analysis": {},
        "portfolio_management": {
            "current_allocation_pct": current_allocation,
            "remaining_capacity_pct": 20.0 - current_allocation,
            "diversification_impact": "Low" if current_allocation < 5 else "Medium" if current_allocation < 15 else "High",
            "position_sizing_available": True
        },
        "option_strategy_fit": {
            "weekly_wheel_suitability": "High" if grade in ["EXCELLENT", "GOOD"] else "Medium",
            "assignment_tolerance": f"High ({criteria.get('max_assignment_prob', 50)}% max)" if grade == "EXCELLENT" else f"Moderate ({criteria.get('max_assignment_prob', 40)}% max)",
            "return_expectation": f"≥{criteria.get('min_annualized_return', 20)}% annualized"
        },
        "risk_factors": [],
        "positive_factors": []
    }
    
    # Add technical analysis if available
    if technical_data:
        indicators = technical_data.get('technical_indicators', {})
        signals = technical_data.get('signals', [])
        
        reasoning["technical_analysis"] = {
            "rsi": indicators.get('rsi'),
            "rsi_interpretation": "Neutral" if 30 <= indicators.get('rsi', 50) <= 70 else 
                                 "Overbought" if indicators.get('rsi', 50) > 70 else "Oversold",
            "volume_ratio": indicators.get('volume_ratio'),
            "volume_assessment": "High" if indicators.get('volume_ratio', 0) > 0.8 else
                               "Medium" if indicators.get('volume_ratio', 0) > 0.5 else "Low",
            "trend_signals": signals,
            "trend_bias": "Bullish" if any("BULLISH" in s or "ABOVE" in s for s in signals) else
                         "Bearish" if any("BEARISH" in s or "BELOW" in s for s in signals) else "Neutral"
        }
        
        # Add positive factors
        if indicators.get('rsi', 50) < 70:
            reasoning["positive_factors"].append(f"RSI {indicators.get('rsi', 'N/A'):.1f} - not overbought")
        
        if any("BULLISH ALIGNMENT" in s for s in signals):
            reasoning["positive_factors"].append("Bullish EMA alignment - strong trend")
            
        if any("ABOVE LONG-TERM EMA" in s for s in signals):
            reasoning["positive_factors"].append("Above long-term EMA - uptrend intact")
            
        if indicators.get('volume_ratio', 0) > 0.5:
            reasoning["positive_factors"].append(f"Good liquidity (volume ratio {indicators.get('volume_ratio', 0):.2f})")
        
        # Add risk factors
        if indicators.get('rsi', 50) > 75:
            reasoning["risk_factors"].append(f"Elevated RSI {indicators.get('rsi', 'N/A'):.1f} - potential pullback")
            
        if any("DOWNTREND" in s for s in signals):
            reasoning["risk_factors"].append("Technical downtrend signals present")
    
    # Add grade-specific factors
    if grade == "EXCELLENT":
        reasoning["positive_factors"].extend([
            "Excellent fundamental grade - high quality underlying",
            "Lower return requirement due to quality (≥15% vs ≥25%+ for others)",
            "Higher assignment tolerance - we want to own this stock"
        ])
    elif grade == "GOOD":
        reasoning["positive_factors"].append("Solid fundamental grade - good quality underlying")
        reasoning["risk_factors"].append("Higher return requirement (≥25%) due to moderate grade")
    
    # Portfolio factors
    if current_allocation < 5:
        reasoning["positive_factors"].append("Low current allocation - plenty of diversification room")
    elif current_allocation > 15:
        reasoning["risk_factors"].append("Higher allocation - approaching concentration limit")
    
    return reasoning

def run_put_selection():
    """Run the complete put selection process and save results."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Save raw recommendations to new folder structure
    raw_output_file = Path("data/option_search/puts/raw_recs") / f"put_recommendations_{timestamp}.json"
    final_output_file = Path("data/option_search/puts/final_recs") / f"top_puts_{timestamp}.json"
    
    # Ensure directories exist
    raw_output_file.parent.mkdir(parents=True, exist_ok=True)
    final_output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Setup logging
    setup_logging('INFO')
    
    print("🚀 Starting Weekly Put Selection Engine")
    print("=" * 50)
    
    # Initialize client - try real client first, fall back to simulation
    client = None
    try:
        # Load Schwab configuration for real API usage
        config = SchwabConfig.from_env()
        
        if config.is_valid():
            print("📡 Initializing Schwab client...")
            client = RealBrokerClient(
                app_key=config.app_key,
                app_secret=config.app_secret,
                redirect_uri=config.redirect_uri,
                token_path=config.token_path
            )
            print("✅ Real Schwab client initialized")
        else:
            print("⚠️  No valid Schwab credentials found, using simulation mode")
            client = SimBrokerClient()
    except Exception as e:
        print(f"⚠️  Failed to initialize real client ({e}), using simulation mode")
        client = SimBrokerClient()
    
    # Load account snapshot
    print("📊 Loading account snapshot...")
    account_snapshot = load_account_snapshot()
    print(f"   Account value: ${account_snapshot.official_liquidation_value:,.2f}")
    print(f"   Available cash: ${account_snapshot.cash:,.2f}")
    
    # Initialize put selection engine
    print("🎯 Initializing put selection engine...")
    engine = PutSelectionEngine(client=client, data_dir="data", max_total_allocation_pct=20.0)
    
    # Load supporting data for reasoning
    allocations = engine._load_account_allocations()
    technical_data = engine._load_technical_data()
    current_options = engine._load_current_option_positions()
    
    print(f"   Loaded {len(allocations)} allocation records")
    print(f"   Loaded {len(technical_data)} technical profiles") 
    print(f"   Found {len(current_options)} symbols with existing options")
    
    # Get eligible symbols
    print("\n🔍 Finding eligible symbols...")
    eligible_symbols = engine._get_eligible_symbols()
    print(f"   Found {len(eligible_symbols)} eligible symbols for analysis")
    
    if not eligible_symbols:
        print("❌ No eligible symbols found. Check filters and data.")
        return
    
    # Prepare comprehensive results
    results = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "strategy": "weekly_cash_secured_puts",
            "account_value": str(account_snapshot.official_liquidation_value),
            "available_cash": str(account_snapshot.cash),
            "max_allocation_per_symbol": 20.0,
            "time_horizon": "1-10 days (weekly options)",
            "data_sources": {
                "account_snapshot": "data/account/account_snapshot.json",
                "wheel_rankings": "latest wheel_rankings_*.json", 
                "technical_analysis": "integrated from account snapshot"
            }
        },
        "filtering_summary": {
            "initial_candidates": len(engine._load_latest_wheel_rankings()),
            "after_option_filter": 0,  # Will calculate below
            "after_allocation_filter": 0,
            "after_technical_filter": len(eligible_symbols),
            "final_eligible": len(eligible_symbols)
        },
        "eligible_symbols": [],
        "put_recommendations": {},
        "exclusions": {
            "existing_option_positions": [],
            "high_allocation": [],
            "technical_failures": []
        }
    }
    
    # Document exclusions
    rankings = engine._load_latest_wheel_rankings()
    for symbol, ranking_data in rankings.items():
        grade = ranking_data.get('overall_grade', 'UNKNOWN')
        current_allocation = float(allocations.get(symbol, {}).get('total_allocation_pct', '0'))
        
        if symbol in current_options:
            positions = []
            for pos in current_options[symbol]:
                positions.append({
                    "type": pos.get('put_call', 'UNKNOWN'),
                    "quantity": pos.get('qty', 0),
                    "strike": pos.get('strike', 'N/A'),
                    "expiry": pos.get('expiry', 'N/A')[:10] if pos.get('expiry') else 'N/A'
                })
            results["exclusions"]["existing_option_positions"].append({
                "symbol": symbol,
                "grade": grade,
                "positions": positions
            })
        elif current_allocation >= 20.0:
            results["exclusions"]["high_allocation"].append({
                "symbol": symbol,
                "grade": grade,
                "allocation_pct": current_allocation
            })
    
    # Process eligible symbols
    print("\n📋 Processing eligible symbols...")
    for symbol, grade, current_allocation in eligible_symbols:
        print(f"   Analyzing {symbol} ({grade}, {current_allocation:.1f}% allocated)")
        
        # Get detailed reasoning
        symbol_technical = technical_data.get(symbol, {})
        criteria = engine.grade_criteria[grade]
        reasoning = generate_selection_reasoning(symbol, grade, symbol_technical, current_allocation, criteria)
        
        # Add to eligible symbols list
        eligible_info = {
            "symbol": symbol,
            "grade": grade,
            "current_allocation_pct": current_allocation,
            "remaining_capacity_pct": 20.0 - current_allocation,
            "selection_reasoning": reasoning,
            "criteria": {
                "min_annualized_return_pct": criteria.get('min_annualized_return', 0),
                "min_downside_protection_pct": criteria.get('min_downside_protection', 0),
                "max_assignment_probability_pct": criteria.get('max_assignment_prob', 0),
                "preferred_dte_range": criteria.get('preferred_dte_range', [1, 10]),
                "technical_requirements": {
                    "rsi_range": [criteria.get('min_rsi', 0), criteria.get('max_rsi', 100)],
                    "min_volume_ratio": criteria.get('volume_ratio_min', 0),
                    "required_signals": criteria.get('required_signals', [])
                }
            }
        }
        
        results["eligible_symbols"].append(eligible_info)
    
    # Run put analysis with available client
    if hasattr(client, 'client') and client.client is not None:
        print("\n📊 Analyzing live put opportunities...")
        try:
            recommendations = engine.get_recommended_puts(account_snapshot, min_score=40.0)
            
            # Convert to our output format
            for symbol, rec_data in recommendations.items():
                results["put_recommendations"][symbol] = {
                    "symbol": symbol,
                    "grade": rec_data.get("grade", "UNKNOWN"),
                    "analysis_status": "live_data",
                    "current_price": rec_data.get("current_price", 0),
                    "recommended_puts": rec_data.get("recommended_puts", []),
                    "total_opportunities": rec_data.get("total_opportunities", 0),
                    "min_score_applied": rec_data.get("min_score_applied", 40.0),
                    "analysis_timestamp": rec_data.get("analysis_timestamp"),
                    "analysis_notes": [
                        "Live market data analysis",
                        f"Applied {rec_data.get('grade', 'UNKNOWN')} grade criteria",
                        f"Minimum attractiveness score: {rec_data.get('min_score_applied', 40.0)}"
                    ]
                }
        except Exception as e:
            print(f"⚠️  Live analysis failed ({e}), falling back to simulation...")
            client = SimBrokerClient()  # Fall back to simulation
    
    # Use simulation if no real client available
    if not hasattr(client, 'client') or client.client is None:
        print("\n⚠️  Simulation Mode: Generating mock put recommendations...")
        
        for symbol, grade, current_allocation in eligible_symbols:
            criteria = engine.grade_criteria[grade]
            remaining_pct = 20.0 - current_allocation
            
            # Create mock put recommendations
            mock_puts = []
            base_return = criteria.get('min_annualized_return', 20)
            
            for i, dte in enumerate([3, 7, 10]):
                mock_put = {
                    "rank": i + 1,
                    "symbol": symbol,
                    "strike_price": 95.0 + i * 2,  # Mock strikes
                    "premium": 1.25 + i * 0.25,    # Mock premiums  
                    "days_to_expiry": dte,
                    "expiration_date": f"2025-10-{10 + dte}",
                    "annualized_return_pct": base_return + i * 5,
                    "downside_protection_pct": 3.0 + i * 1.0,
                    "assignment_probability_pct": 25 + i * 5,
                    "attractiveness_score": 85 - i * 5,
                    "collateral_required": (95.0 + i * 2) * 100,
                    "max_contracts": int((float(account_snapshot.official_liquidation_value) * remaining_pct / 100) / ((95.0 + i * 2) * 100)),
                    "simulated": True,
                    "recommendation_reason": f"Mock data - {dte} day expiry with {base_return + i * 5:.1f}% return"
                }
                mock_puts.append(mock_put)
            
            results["put_recommendations"][symbol] = {
                "symbol": symbol,
                "grade": grade,
                "analysis_status": "simulated",
                "recommended_puts": mock_puts,
                "analysis_notes": [
                    "This is simulated data for development/testing",
                    f"Real analysis requires live API connection",
                    f"Symbol meets all filtering criteria for {grade} grade"
                ]
            }
    
    # Update filtering summary
    results["filtering_summary"]["after_option_filter"] = len(rankings) - len(results["exclusions"]["existing_option_positions"])
    results["filtering_summary"]["after_allocation_filter"] = results["filtering_summary"]["after_option_filter"] - len(results["exclusions"]["high_allocation"])
    
    # Save raw results
    print(f"\n💾 Saving raw results to {raw_output_file}")
    with open(raw_output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    # Generate final selections (top choice per stock)
    final_results = generate_final_selections(results, timestamp)
    
    print(f"💾 Saving final selections to {final_output_file}")
    with open(final_output_file, 'w') as f:
        json.dump(final_results, f, indent=2, default=str)
    
    # Print summary
    print(f"\n🎉 Put Selection Complete!")
    print(f"   Eligible symbols: {len(eligible_symbols)}")
    print(f"   Recommendations generated: {len(results['put_recommendations'])}")
    print(f"   Raw results saved to: {raw_output_file}")
    print(f"   Final selections saved to: {final_output_file}")
    
    # Print key recommendations
    if results["put_recommendations"]:
        print(f"\n⭐ Top Recommendations:")
        for symbol, rec_data in results["put_recommendations"].items():
            grade = rec_data.get("grade", "UNKNOWN")
            puts = rec_data.get("recommended_puts", [])
            if puts:
                top_put = puts[0]
                return_pct = top_put.get("annualized_return_pct", 0)
                dte = top_put.get("days_to_expiry", 0)
                strike = top_put.get("strike_price", 0)
                print(f"   {symbol} ({grade}): ${strike} put, {dte}d, {return_pct:.1f}% return")

def main():
    """Main execution function."""
    try:
        run_put_selection()
    except KeyboardInterrupt:
        print("\n❌ Put selection cancelled by user")
    except Exception as e:
        print(f"\n❌ Error during put selection: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()