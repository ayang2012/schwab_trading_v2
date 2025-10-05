#!/usr/bin/env python3
"""
Wheel Strategy Ranking System

Reads the latest watchlist analysis JSON file and ranks stocks for:
- Cash-secured put selling opportunities  
- Covered call selling opportunities

Uses configurable criteria from settings.py to score and rank candidates.
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple
import sys

# Add project root to path for imports
sys.path.append(str(Path(__file__).parent.parent))

try:
    from config import settings
    from utils.logging import setup_logging, get_logger
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


class WheelRanker:
    """Ranks wheel strategy candidates from watchlist technical analysis."""
    
    def __init__(self):
        self.logger = get_logger()
        self.config = settings
        
    def find_latest_watchlist_file(self, data_dir: str = None) -> Path:
        """Find the most recent watchlist analysis file."""
        if data_dir is None:
            data_dir = getattr(self.config, 'WATCHLIST_OUTPUT_DIR', 'data/stock_watchlist')
        
        data_path = Path(data_dir)
        
        if not data_path.exists():
            raise FileNotFoundError(f"Watchlist directory not found: {data_dir}")
        
        # Find all watchlist files (both old and new patterns)
        patterns = ["watchlist_significant_alerts_*.json", "watchlist_*.json"]
        watchlist_files = []
        
        for pattern in patterns:
            watchlist_files.extend(list(data_path.glob(pattern)))
        
        if not watchlist_files:
            raise FileNotFoundError(f"No watchlist files found in {data_dir}")
        
        # Sort by modification time, get the latest
        latest_file = max(watchlist_files, key=lambda f: f.stat().st_mtime)
        
        return latest_file
    
    def load_watchlist_data(self, file_path: Path) -> Dict[str, Any]:
        """Load and parse watchlist JSON data."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            self.logger.info(f"📂 Loaded watchlist data from: {file_path.name}")
            return data
            
        except Exception as e:
            self.logger.error(f"Failed to load watchlist data: {e}")
            raise
    
    def calculate_put_score(self, symbol: str, tech_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate put selling score for a stock."""
        weights = getattr(self.config, 'PUT_RANKING_WEIGHTS', {})
        
        rsi = tech_data.get('rsi', 50)
        price_change_pct = abs(tech_data.get('price_change_pct', 0))
        volume_ratio = tech_data.get('volume_ratio', 1.0)
        current_price = tech_data.get('market_price', tech_data.get('current_price', 0))
        
        breakdown = {}
        total_score = 0
        
        # RSI Score (25 points) - Ideal range for put selling
        rsi_excellent = getattr(self.config, 'PUT_RSI_EXCELLENT', (30, 45))
        rsi_good = getattr(self.config, 'PUT_RSI_GOOD', (25, 55))
        rsi_fair = getattr(self.config, 'PUT_RSI_FAIR', (20, 60))
        
        if rsi_excellent[0] <= rsi <= rsi_excellent[1]:
            rsi_score = weights.get('rsi_score', 25)
            rsi_desc = "EXCELLENT"
        elif rsi_good[0] <= rsi <= rsi_good[1]:
            rsi_score = weights.get('rsi_score', 25) * 0.8
            rsi_desc = "GOOD"
        elif rsi_fair[0] <= rsi <= rsi_fair[1]:
            rsi_score = weights.get('rsi_score', 25) * 0.5
            rsi_desc = "FAIR"
        else:
            rsi_score = 0
            rsi_desc = "AVOID"
        
        breakdown['rsi'] = f"{rsi_score:.1f}/25 ({rsi_desc}: RSI {rsi:.1f})"
        total_score += rsi_score
        
        # Price Stability Score (20 points)
        stability_thresholds = [
            (getattr(self.config, 'STABILITY_EXCELLENT', 1.0), 1.0, "EXCELLENT"),
            (getattr(self.config, 'STABILITY_GOOD', 2.0), 0.8, "GOOD"),
            (getattr(self.config, 'STABILITY_FAIR', 3.5), 0.5, "FAIR"),
            (getattr(self.config, 'STABILITY_POOR', 5.0), 0.2, "POOR")
        ]
        
        stability_score = 0
        stability_desc = "VOLATILE"
        for threshold, multiplier, desc in stability_thresholds:
            if price_change_pct < threshold:
                stability_score = weights.get('price_stability', 20) * multiplier
                stability_desc = desc
                break
        
        breakdown['stability'] = f"{stability_score:.1f}/20 ({stability_desc}: {price_change_pct:.1f}% move)"
        total_score += stability_score
        
        # Support Level Score (15 points) - Based on technical indicators
        support_level = tech_data.get('support_level', current_price * 0.95)
        distance_from_support = ((current_price - support_level) / support_level) * 100 if support_level > 0 else 0
        
        if distance_from_support < 5:  # Close to support
            support_score = weights.get('support_level', 15) * 0.9
            support_desc = "NEAR SUPPORT"
        elif distance_from_support < 10:
            support_score = weights.get('support_level', 15) * 0.7
            support_desc = "MODERATE"
        else:
            support_score = weights.get('support_level', 15) * 0.5
            support_desc = "FAR FROM SUPPORT"
        
        breakdown['support'] = f"{support_score:.1f}/15 ({support_desc}: {distance_from_support:.1f}% above)"
        total_score += support_score
        
        # Volume Score (10 points)
        volume_excellent = getattr(self.config, 'VOLUME_EXCELLENT', (0.8, 2.0))
        volume_good = getattr(self.config, 'VOLUME_GOOD', (0.5, 3.0))
        
        if volume_excellent[0] <= volume_ratio <= volume_excellent[1]:
            volume_score = weights.get('volume_score', 10)
            volume_desc = "EXCELLENT"
        elif volume_good[0] <= volume_ratio <= volume_good[1]:
            volume_score = weights.get('volume_score', 10) * 0.8
            volume_desc = "GOOD"
        else:
            volume_score = weights.get('volume_score', 10) * 0.5
            volume_desc = "FAIR"
        
        breakdown['volume'] = f"{volume_score:.1f}/10 ({volume_desc}: {volume_ratio:.1f}x avg)"
        total_score += volume_score
        
        # Trend Score (15 points) - Based on moving averages and signals
        signals = tech_data.get('signals', [])
        ema_10 = tech_data.get('ema_10', current_price)
        ema_20 = tech_data.get('ema_20', current_price)
        
        if any('OVERSOLD' in signal for signal in signals):
            trend_score = weights.get('trend_score', 15) * 0.9
            trend_desc = "OVERSOLD - GOOD"
        elif current_price > ema_10 > ema_20:
            trend_score = weights.get('trend_score', 15) * 0.7
            trend_desc = "UPTREND - OK"
        elif ema_10 < ema_20:
            trend_score = weights.get('trend_score', 15) * 0.4
            trend_desc = "DOWNTREND - RISKY"
        else:
            trend_score = weights.get('trend_score', 15) * 0.6
            trend_desc = "SIDEWAYS"
        
        breakdown['trend'] = f"{trend_score:.1f}/15 ({trend_desc})"
        total_score += trend_score
        
        # Bollinger Position (10 points)
        bb_bands = tech_data.get('bollinger_bands', {})
        bb_upper = bb_bands.get('upper', current_price * 1.1)
        bb_lower = bb_bands.get('lower', current_price * 0.9)
        bb_middle = bb_bands.get('middle', current_price)
        
        if bb_lower <= current_price <= bb_middle:
            bb_score = weights.get('bollinger_position', 10) * 0.9
            bb_desc = "LOWER HALF - GOOD"
        elif current_price < bb_lower:
            bb_score = weights.get('bollinger_position', 10) * 0.8
            bb_desc = "BELOW LOWER - OK"  
        else:
            bb_score = weights.get('bollinger_position', 10) * 0.5
            bb_desc = "UPPER HALF - RISKY"
        
        breakdown['bollinger'] = f"{bb_score:.1f}/10 ({bb_desc})"
        total_score += bb_score
        
        # MACD Score (5 points) - Simplified
        macd_score = weights.get('macd_score', 5) * 0.7  # Neutral assumption
        breakdown['macd'] = f"{macd_score:.1f}/5 (NEUTRAL)"
        total_score += macd_score
        
        # Determine grade
        if total_score >= getattr(self.config, 'RANK_EXCELLENT', 80):
            grade = "EXCELLENT"
        elif total_score >= getattr(self.config, 'RANK_GOOD', 65):
            grade = "GOOD"
        elif total_score >= getattr(self.config, 'RANK_FAIR', 50):
            grade = "FAIR"
        elif total_score >= getattr(self.config, 'RANK_POOR', 35):
            grade = "POOR"
        else:
            grade = "AVOID"
        
        return {
            "symbol": symbol,
            "score": round(total_score, 1),
            "grade": grade,
            "breakdown": breakdown,
            "strategy": "cash_secured_put",
            "rsi": rsi,
            "price": current_price,
            "price_change": tech_data.get('price_change_pct', 0)
        }
    
    def calculate_call_score(self, symbol: str, tech_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate call selling score for a stock."""
        weights = getattr(self.config, 'CALL_RANKING_WEIGHTS', {})
        
        rsi = tech_data.get('rsi', 50)
        price_change_pct = tech_data.get('price_change_pct', 0)
        volume_ratio = tech_data.get('volume_ratio', 1.0)
        current_price = tech_data.get('market_price', tech_data.get('current_price', 0))
        
        breakdown = {}
        total_score = 0
        
        # RSI Score (25 points) - Ideal range for call selling
        rsi_excellent = getattr(self.config, 'CALL_RSI_EXCELLENT', (65, 75))
        rsi_good = getattr(self.config, 'CALL_RSI_GOOD', (60, 80))
        rsi_fair = getattr(self.config, 'CALL_RSI_FAIR', (55, 85))
        
        if rsi_excellent[0] <= rsi <= rsi_excellent[1]:
            rsi_score = weights.get('rsi_score', 25)
            rsi_desc = "EXCELLENT"
        elif rsi_good[0] <= rsi <= rsi_good[1]:
            rsi_score = weights.get('rsi_score', 25) * 0.8
            rsi_desc = "GOOD"
        elif rsi_fair[0] <= rsi <= rsi_fair[1]:
            rsi_score = weights.get('rsi_score', 25) * 0.5
            rsi_desc = "FAIR"
        else:
            rsi_score = 0
            rsi_desc = "AVOID"
        
        breakdown['rsi'] = f"{rsi_score:.1f}/25 ({rsi_desc}: RSI {rsi:.1f})"
        total_score += rsi_score
        
        # Resistance Level Score (20 points)
        resistance_level = tech_data.get('resistance_level', current_price * 1.05)
        distance_to_resistance = ((resistance_level - current_price) / current_price) * 100 if current_price > 0 else 0
        
        if distance_to_resistance < 3:  # Close to resistance
            resistance_score = weights.get('resistance_level', 20) * 0.9
            resistance_desc = "NEAR RESISTANCE"
        elif distance_to_resistance < 7:
            resistance_score = weights.get('resistance_level', 20) * 0.7
            resistance_desc = "MODERATE"
        else:
            resistance_score = weights.get('resistance_level', 20) * 0.5
            resistance_desc = "FAR FROM RESISTANCE"
        
        breakdown['resistance'] = f"{resistance_score:.1f}/20 ({resistance_desc}: {distance_to_resistance:.1f}% below)"
        total_score += resistance_score
        
        # Price Momentum Score (15 points) - Upward momentum good for calls
        if price_change_pct > 3:
            momentum_score = weights.get('price_momentum', 15)
            momentum_desc = "STRONG UP"
        elif price_change_pct > 1:
            momentum_score = weights.get('price_momentum', 15) * 0.8
            momentum_desc = "MODERATE UP"
        elif price_change_pct > 0:
            momentum_score = weights.get('price_momentum', 15) * 0.6
            momentum_desc = "SLIGHT UP"
        else:
            momentum_score = weights.get('price_momentum', 15) * 0.3
            momentum_desc = "NO MOMENTUM"
        
        breakdown['momentum'] = f"{momentum_score:.1f}/15 ({momentum_desc}: {price_change_pct:+.1f}%)"
        total_score += momentum_score
        
        # Volume Score (10 points) - Same as puts
        volume_excellent = getattr(self.config, 'VOLUME_EXCELLENT', (0.8, 2.0))
        volume_good = getattr(self.config, 'VOLUME_GOOD', (0.5, 3.0))
        
        if volume_excellent[0] <= volume_ratio <= volume_excellent[1]:
            volume_score = weights.get('volume_score', 10)
            volume_desc = "EXCELLENT"
        elif volume_good[0] <= volume_ratio <= volume_good[1]:
            volume_score = weights.get('volume_score', 10) * 0.8
            volume_desc = "GOOD"
        else:
            volume_score = weights.get('volume_score', 10) * 0.5
            volume_desc = "FAIR"
        
        breakdown['volume'] = f"{volume_score:.1f}/10 ({volume_desc}: {volume_ratio:.1f}x avg)"
        total_score += volume_score
        
        # Trend Exhaustion Score (15 points)
        signals = tech_data.get('signals', [])
        
        if any('OVERBOUGHT' in signal for signal in signals) and rsi > 70:
            exhaustion_score = weights.get('trend_exhaustion', 15) * 0.9
            exhaustion_desc = "OVERBOUGHT - GOOD"
        elif rsi > 65:
            exhaustion_score = weights.get('trend_exhaustion', 15) * 0.7
            exhaustion_desc = "GETTING EXTENDED"
        else:
            exhaustion_score = weights.get('trend_exhaustion', 15) * 0.4
            exhaustion_desc = "NOT EXTENDED"
        
        breakdown['exhaustion'] = f"{exhaustion_score:.1f}/15 ({exhaustion_desc})"
        total_score += exhaustion_score
        
        # Bollinger Position (10 points) - Upper band good for calls
        bb_bands = tech_data.get('bollinger_bands', {})
        bb_upper = bb_bands.get('upper', current_price * 1.1)
        bb_middle = bb_bands.get('middle', current_price)
        
        if current_price >= bb_middle:
            bb_score = weights.get('bollinger_position', 10) * 0.8
            bb_desc = "UPPER HALF - GOOD"
        elif current_price >= bb_upper:
            bb_score = weights.get('bollinger_position', 10) * 0.9
            bb_desc = "NEAR UPPER - EXCELLENT"
        else:
            bb_score = weights.get('bollinger_position', 10) * 0.4
            bb_desc = "LOWER HALF - POOR"
        
        breakdown['bollinger'] = f"{bb_score:.1f}/10 ({bb_desc})"
        total_score += bb_score
        
        # MACD Score (5 points) - Simplified
        macd_score = weights.get('macd_score', 5) * 0.6
        breakdown['macd'] = f"{macd_score:.1f}/5 (NEUTRAL)"
        total_score += macd_score
        
        # Determine grade
        if total_score >= getattr(self.config, 'RANK_EXCELLENT', 80):
            grade = "EXCELLENT"
        elif total_score >= getattr(self.config, 'RANK_GOOD', 65):
            grade = "GOOD"
        elif total_score >= getattr(self.config, 'RANK_FAIR', 50):
            grade = "FAIR"
        elif total_score >= getattr(self.config, 'RANK_POOR', 35):
            grade = "POOR"
        else:
            grade = "AVOID"
        
        return {
            "symbol": symbol,
            "score": round(total_score, 1),
            "grade": grade,
            "breakdown": breakdown,
            "strategy": "covered_call",
            "rsi": rsi,
            "price": current_price,
            "price_change": price_change_pct
        }
    
    def rank_wheel_candidates(self, watchlist_data: Dict[str, Any]) -> Dict[str, Any]:
        """Rank all stocks for wheel strategy opportunities."""
        watchlist_stocks = watchlist_data.get("watchlist_stocks", {})
        
        put_candidates = []
        call_candidates = []
        
        self.logger.info(f"🔍 Ranking {len(watchlist_stocks)} stocks for wheel opportunities...")
        
        for symbol, tech_data in watchlist_stocks.items():
            if 'error' in tech_data:
                self.logger.debug(f"Skipping {symbol}: {tech_data['error']}")
                continue
            
            # Calculate put selling score
            put_score_data = self.calculate_put_score(symbol, tech_data)
            min_score = getattr(self.config, 'MIN_RANKING_SCORE', 35)
            
            if put_score_data['score'] >= min_score:
                put_candidates.append(put_score_data)
            
            # Calculate call selling score
            call_score_data = self.calculate_call_score(symbol, tech_data)
            
            if call_score_data['score'] >= min_score:
                call_candidates.append(call_score_data)
        
        # Sort by score (highest first)
        put_candidates.sort(key=lambda x: x['score'], reverse=True)
        call_candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # Limit results
        max_puts = getattr(self.config, 'MAX_PUT_RANKINGS', 5)
        max_calls = getattr(self.config, 'MAX_CALL_RANKINGS', 5)
        
        return {
            "put_candidates": put_candidates[:max_puts],
            "call_candidates": call_candidates[:max_calls],
            "summary": {
                "total_put_candidates": len(put_candidates),
                "total_call_candidates": len(call_candidates),
                "top_put_score": put_candidates[0]['score'] if put_candidates else 0,
                "top_call_score": call_candidates[0]['score'] if call_candidates else 0,
                "generated_at": datetime.now().isoformat()
            }
        }
    
    def display_rankings(self, rankings: Dict[str, Any]):
        """Display ranked wheel candidates in formatted tables."""
        summary = rankings.get('summary', {})
        
        self.logger.info("🏆 WHEEL STRATEGY RANKINGS")
        self.logger.info(f"📊 Generated: {summary.get('generated_at', 'Unknown')}")
        self.logger.info(f"📈 Total Candidates: {summary.get('total_put_candidates', 0)} puts, {summary.get('total_call_candidates', 0)} calls")
        
        # Display PUT rankings
        put_candidates = rankings.get('put_candidates', [])
        if put_candidates:
            self.logger.info(f"\n💰 CASH-SECURED PUTS RANKINGS (Top {len(put_candidates)}):")
            self.logger.info("─" * 85)
            self.logger.info(f"{'Rank':<4} {'Symbol':<6} {'Score':<6} {'Grade':<9} {'RSI':<6} {'Price':<8} {'Change':<7}")
            self.logger.info("─" * 85)
            
            for i, candidate in enumerate(put_candidates, 1):
                grade_emoji = {"EXCELLENT": "🟢", "GOOD": "🟡", "FAIR": "🟠", "POOR": "🔴"}.get(candidate['grade'], "⚪")
                self.logger.info(
                    f"{i:<4} {candidate['symbol']:<6} {candidate['score']:<6.1f} "
                    f"{grade_emoji}{candidate['grade']:<8} {candidate['rsi']:<6.1f} "
                    f"${candidate['price']:<7.2f} {candidate['price_change']:+.1f}%"
                )
            
            # Show breakdown for top candidate
            if getattr(self.config, 'SHOW_RANKING_BREAKDOWN', True) and put_candidates:
                top_put = put_candidates[0]
                self.logger.info(f"\n🔍 TOP PUT BREAKDOWN ({top_put['symbol']} - {top_put['score']:.1f}/100):")
                for component, details in top_put['breakdown'].items():
                    self.logger.info(f"   • {component.title()}: {details}")
        
        # Display CALL rankings
        call_candidates = rankings.get('call_candidates', [])
        if call_candidates:
            self.logger.info(f"\n📞 COVERED CALLS RANKINGS (Top {len(call_candidates)}):")
            self.logger.info("─" * 85)
            self.logger.info(f"{'Rank':<4} {'Symbol':<6} {'Score':<6} {'Grade':<9} {'RSI':<6} {'Price':<8} {'Change':<7}")
            self.logger.info("─" * 85)
            
            for i, candidate in enumerate(call_candidates, 1):
                grade_emoji = {"EXCELLENT": "🟢", "GOOD": "🟡", "FAIR": "🟠", "POOR": "🔴"}.get(candidate['grade'], "⚪")
                self.logger.info(
                    f"{i:<4} {candidate['symbol']:<6} {candidate['score']:<6.1f} "
                    f"{grade_emoji}{candidate['grade']:<8} {candidate['rsi']:<6.1f} "
                    f"${candidate['price']:<7.2f} {candidate['price_change']:+.1f}%"
                )
            
            # Show breakdown for top candidate
            if getattr(self.config, 'SHOW_RANKING_BREAKDOWN', True) and call_candidates:
                top_call = call_candidates[0]
                self.logger.info(f"\n🔍 TOP CALL BREAKDOWN ({top_call['symbol']} - {top_call['score']:.1f}/100):")
                for component, details in top_call['breakdown'].items():
                    self.logger.info(f"   • {component.title()}: {details}")
        
        if not put_candidates and not call_candidates:
            self.logger.warning("❌ No candidates found meeting minimum score criteria")
            
        self.logger.info(f"\n📊 Best Scores: Puts {summary.get('top_put_score', 0):.1f}/100, Calls {summary.get('top_call_score', 0):.1f}/100")


def main():
    parser = argparse.ArgumentParser(description="Rank wheel strategy candidates from latest watchlist data")
    parser.add_argument("--data-dir", help="Directory containing watchlist JSON files (default: data/stock_watchlist)")
    parser.add_argument("--file", help="Specific watchlist JSON file to analyze")
    parser.add_argument("--output", help="Save rankings to JSON file (default: data/stock_ranking/wheel_rankings_TIMESTAMP.json)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet mode - minimal output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose mode - detailed output")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = "ERROR" if args.quiet else "DEBUG" if args.verbose else "INFO"
    setup_logging(level=log_level, quiet=args.quiet)
    
    try:
        ranker = WheelRanker()
        
        # Find or use specified file
        if args.file:
            watchlist_file = Path(args.file)
            if not watchlist_file.exists():
                raise FileNotFoundError(f"Specified file not found: {args.file}")
        else:
            watchlist_file = ranker.find_latest_watchlist_file(args.data_dir)
        
        # Load and rank data
        watchlist_data = ranker.load_watchlist_data(watchlist_file)
        rankings = ranker.rank_wheel_candidates(watchlist_data)
        
        # Display results
        if not args.quiet:
            ranker.display_rankings(rankings)
        
        # Save output (either specified file or default location)
        if args.output:
            output_path = Path(args.output)
        else:
            # Default to organized ranking directory
            ranking_dir = getattr(ranker.config, 'RANKING_OUTPUT_DIR', 'data/stock_ranking')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"wheel_rankings_{timestamp}.json"
            output_path = Path(ranking_dir) / filename
        
        # Ensure directory exists and save
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(rankings, f, indent=2)
        
        if not args.quiet:
            ranker.logger.info(f"💾 Rankings saved to: {output_path}")
        
        return 0
        
    except Exception as e:
        logger = get_logger()
        logger.error(f"Ranking failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())