#!/usr/bin/env python3
"""Live trading monitor - runs every 20 seconds during market hours."""

import time
import argparse
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import List, Dict, Any

try:
    # Try relative imports first (when run as module from parent)
    from .api.client import RealBrokerClient 
    from .api.sim_client import SimBrokerClient
    from .utils.config_schwab import SchwabConfig
    from .core.orchestrator import run_once
    from .utils.logging import setup_logging
    from .analysis.technicals import get_technicals_for_symbol
    from .utils.io import safe_write_json
except ImportError:
    # Fall back to direct imports (when run from within directory)
    from api.client import RealBrokerClient
    from api.sim_client import SimBrokerClient
    from utils.config_schwab import SchwabConfig
    from core.orchestrator import run_once
    from utils.logging import setup_logging
    from analysis.technicals import get_technicals_for_symbol
    from utils.io import safe_write_json


def load_watchlist_from_config(config_path: str) -> List[str]:
    """Load watchlist symbols from configuration file."""
    try:
        import sys
        import importlib.util
        from pathlib import Path
        
        config_file = Path(config_path)
        if not config_file.exists():
            return []
        
        spec = importlib.util.spec_from_file_location("settings", config_file)
        config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config)
        
        # Try to get the active watchlist
        symbols = getattr(config, 'ACTIVE_WATCHLIST', [])
        if not symbols:
            symbols = getattr(config, 'WATCHLIST_STOCKS', [])
        
        return symbols
        
    except Exception as e:
        print(f"Error loading watchlist from {config_path}: {e}")
        return []


def analyze_watchlist_technicals(client, symbols: List[str]) -> Dict[str, Any]:
    """Analyze technical indicators for a list of watchlist symbols."""
    results = {
        "watchlist_stocks": {},
        "summary": {
            "total_watchlist_analyzed": len(symbols),
            "successful_analyses": 0,
            "failed_analyses": 0,
            "watchlist_signals": {}
        }
    }
    
    for symbol in symbols:
        try:
            # Use the existing get_technicals_for_symbol function
            tech_data = get_technicals_for_symbol(symbol, client)
            
            if tech_data and not tech_data.get('error'):
                results["watchlist_stocks"][symbol] = tech_data
                results["summary"]["successful_analyses"] += 1
                
                # Count signals for summary
                signals = tech_data.get('signals', [])
                for signal in signals:
                    signal_key = signal.replace(' ', '_').upper()
                    results["summary"]["watchlist_signals"][signal_key] = results["summary"]["watchlist_signals"].get(signal_key, 0) + 1
            else:
                results["watchlist_stocks"][symbol] = {"error": "Failed to get technical data"}
                results["summary"]["failed_analyses"] += 1
                
        except Exception as e:
            results["watchlist_stocks"][symbol] = {"error": str(e)}
            results["summary"]["failed_analyses"] += 1
    
    return results


class LiveTradingMonitor:
    """Monitor account and positions every 20 seconds during trading hours."""
    
    def __init__(self, client, out_dir: Path, interval: int = 20, config_path: str = None, force_run: bool = False):
        self.client = client
        self.out_dir = out_dir
        self.interval = interval
        self.logger = setup_logging(level="INFO")
        self.running = False
        self.config_path = config_path or "config/settings.py"
        self.watchlist_symbols = []
        self.config = None
        self.force_run = force_run  # Bypass market hours check
        
        # Load watchlist
        self._load_watchlist()
    
    def _load_watchlist(self):
        """Load the watchlist from config file."""
        try:
            self.watchlist_symbols = load_watchlist_from_config(self.config_path)
            self._load_config_settings()
            self.logger.info(f"📋 Loaded {len(self.watchlist_symbols)} symbols from watchlist")
            if self.watchlist_symbols:
                self.logger.info(f"   Symbols: {', '.join(self.watchlist_symbols[:10])}{'...' if len(self.watchlist_symbols) > 10 else ''}")
        except Exception as e:
            self.logger.error(f"Failed to load watchlist from {self.config_path}: {e}")
            self.watchlist_symbols = []
    
    def _load_config_settings(self):
        """Load additional configuration settings."""
        try:
            import sys
            from pathlib import Path
            import importlib.util
            
            config_file = Path(self.config_path)
            if config_file.exists():
                spec = importlib.util.spec_from_file_location("settings", config_file)
                self.config = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(self.config)
                self.logger.debug("✅ Configuration settings loaded")
        except Exception as e:
            self.logger.error(f"Failed to load config settings: {e}")
            self.config = None
        
    def is_market_hours(self) -> bool:
        """Check if we're in market hours using config settings."""
        now = datetime.now()
        
        # Get market hours from config or use defaults
        if self.config:
            open_hour = getattr(self.config, 'MARKET_OPEN_HOUR', 6)
            open_minute = getattr(self.config, 'MARKET_OPEN_MINUTE', 30)
            close_hour = getattr(self.config, 'MARKET_CLOSE_HOUR', 13)
            close_minute = getattr(self.config, 'MARKET_CLOSE_MINUTE', 0)
        else:
            open_hour, open_minute = 6, 30
            close_hour, close_minute = 13, 0
        
        market_open = dt_time(open_hour, open_minute)
        market_close = dt_time(close_hour, close_minute)
        current_time = now.time()
        
        # Check if it's a weekday and within market hours
        is_weekday = now.weekday() < 5  # Monday = 0, Friday = 4
        is_market_time = market_open <= current_time <= market_close
        
        return is_weekday and is_market_time
    
    def run_monitoring_cycle(self):
        """Run a single monitoring cycle."""
        try:
            self.logger.info(f"🔄 Running monitoring cycle at {datetime.now().strftime('%H:%M:%S')}")
            
            # 1. Run account analysis (existing logic)
            result = run_once(
                self.client, 
                self.out_dir, 
                include_technicals=True,  # Always include technicals for live monitoring
                check_assignments=True,
                show_positions=False  # Hide stock positions in live monitor
            )
            
            # 2. Run watchlist analysis
            watchlist_result = None
            if self.watchlist_symbols:
                try:
                    self.logger.info(f"📊 Analyzing {len(self.watchlist_symbols)} watchlist stocks...")
                    # Use the client directly (works for both real and simulated clients)
                    client_to_use = self.client.client if hasattr(self.client, 'client') and self.client.client is not None else self.client
                    watchlist_result = analyze_watchlist_technicals(client_to_use, self.watchlist_symbols)
                    self._save_watchlist_analysis(watchlist_result)
                    self._display_watchlist_summary(watchlist_result)
                except Exception as e:
                    self.logger.error(f"Watchlist analysis failed: {e}")
            
            # 3. Run put selection analysis
            put_result = None
            try:
                self.logger.info("🎯 Running put selection analysis...")
                put_result = self._run_put_selection_analysis(result)
            except Exception as e:
                self.logger.error(f"Put selection analysis failed: {e}")
            
            # 4. Check live trading conditions
            self._check_live_trading_conditions(result, watchlist_result)
            
            return {
                'account': result,
                'watchlist': watchlist_result,
                'put_selection': put_result
            }
            
        except Exception as e:
            self.logger.error(f"Error in monitoring cycle: {e}")
            return None
    
    def _save_watchlist_analysis(self, watchlist_result):
        """Save watchlist analysis based on wheel strategy storage settings."""
        if not watchlist_result:
            return

        # Get storage settings from config
        store_every = getattr(self.config, 'STORE_EVERY_ITERATION', False) if self.config else False
        store_eod = getattr(self.config, 'STORE_END_OF_DAY_ONLY', True) if self.config else True
        store_alerts = getattr(self.config, 'STORE_ALERTS_ONLY', True) if self.config else True
        store_interval = getattr(self.config, 'STORE_INTERVAL_MINUTES', 60) if self.config else 60

        should_store = False
        storage_reason = ""

        # Always store if configured to store every iteration
        if store_every:
            should_store = True
            storage_reason = "every_iteration"
        
        # Store at end of day
        elif store_eod and self._is_near_market_close():
            should_store = True
            storage_reason = "end_of_day"
        
        # Store if significant alerts detected
        elif store_alerts and self._has_significant_alerts(watchlist_result):
            should_store = True
            storage_reason = "significant_alerts"
        
        # Store based on time interval
        elif self._should_store_by_interval(store_interval):
            should_store = True
            storage_reason = "timed_interval"

        if should_store:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"watchlist_{storage_reason}_{timestamp}.json"
                
                # Use dedicated watchlist directory
                watchlist_dir = getattr(self.config, 'WATCHLIST_OUTPUT_DIR', 'data/stock_watchlist')
                watchlist_path = Path(watchlist_dir)
                watchlist_path.mkdir(parents=True, exist_ok=True)
                filepath = watchlist_path / filename
                
                # Add metadata to the data
                analysis_data = {
                    "generated_at": datetime.now().isoformat(),
                    "config_path": self.config_path,
                    "storage_reason": storage_reason,
                    "wheel_trading_signals": self._extract_wheel_signals(watchlist_result),
                    **watchlist_result
                }
                
                safe_write_json(filepath, analysis_data)
                self.logger.info(f"💾 Saved watchlist analysis ({storage_reason}): {filename}")
                
                # Generate wheel rankings immediately after saving watchlist data
                try:
                    rankings = self._generate_wheel_rankings(analysis_data)
                    if rankings:
                        self._save_wheel_rankings(rankings, timestamp)
                        self._display_live_rankings(rankings)
                except Exception as e:
                    self.logger.error(f"Failed to generate wheel rankings: {e}")
                
            except Exception as e:
                self.logger.error(f"Failed to save watchlist analysis: {e}")
        else:
            self.logger.debug(f"⏭️  Skipping storage - no significant changes for wheel strategy")

    def _is_near_market_close(self) -> bool:
        """Check if we're within 30 minutes of market close."""
        if not self.config:
            return False
            
        now = datetime.now()
        close_hour = getattr(self.config, 'MARKET_CLOSE_HOUR', 13)
        close_minute = getattr(self.config, 'MARKET_CLOSE_MINUTE', 0)
        
        market_close = now.replace(hour=close_hour, minute=close_minute, second=0, microsecond=0)
        time_to_close = (market_close - now).total_seconds() / 60  # minutes
        
        return 0 <= time_to_close <= 30  # Within 30 minutes of close

    def _has_significant_alerts(self, watchlist_result) -> bool:
        """Check if watchlist has alerts significant for wheel trading."""
        watchlist_stocks = watchlist_result.get("watchlist_stocks", {})
        
        significant_count = 0
        
        for symbol, data in watchlist_stocks.items():
            if 'error' in data:
                continue
                
            # Check for wheel-relevant conditions
            rsi = data.get('rsi', 50)
            price_change = data.get('price_change_pct', 0)
            
            # Conditions that matter for wheel strategy
            if (rsi < 30 or rsi > 70 or  # Oversold/overbought for entry/exit timing
                abs(price_change) > 5):   # Significant price moves
                significant_count += 1
        
        # Consider significant if 20% or more of watchlist has alerts
        return significant_count >= len(watchlist_stocks) * 0.2

    def _should_store_by_interval(self, interval_minutes: int) -> bool:
        """Check if enough time has passed since last storage."""
        # This would track last storage time - simplified for now
        now = datetime.now()
        return now.minute % interval_minutes == 0

    
    
    def _calculate_call_score(self, symbol: str, data: dict) -> dict:
        """Calculate call selling score for a stock."""
        if not self.config:
            return {"score": 0, "breakdown": {}, "grade": "N/A"}
        
        weights = getattr(self.config, 'CALL_SCORING_WEIGHTS', {})
        rsi = data.get('rsi', 50)
        price_change = data.get('price_change_pct', 0)
        price = data.get('current_price', data.get('market_price', 0))  # Use real price field
        
        breakdown = {}
        total_score = 0
        
        # RSI Score (25 points) - Ideal range 65-80 for call selling
        if 65 <= rsi <= 75:
            rsi_score = weights.get('rsi_score', 25)
        elif 60 <= rsi < 65 or 75 < rsi <= 80:
            rsi_score = weights.get('rsi_score', 25) * 0.8
        elif 55 <= rsi < 60 or 80 < rsi <= 85:
            rsi_score = weights.get('rsi_score', 25) * 0.5
        else:
            rsi_score = weights.get('rsi_score', 25) * 0.2
        breakdown['rsi'] = f"{rsi_score:.1f}/25 (RSI: {rsi:.1f})"
        total_score += rsi_score
        
        # Resistance Level Score (20 points) - Mock calculation
        resistance_score = weights.get('resistance_level', 20) * 0.7  # Assume near resistance
        breakdown['resistance'] = f"{resistance_score:.1f}/20 (resistance analysis)"
        total_score += resistance_score
        
        # Price Momentum Score (15 points) - Recent upward movement
        if price_change > 2:
            momentum_score = weights.get('price_momentum', 15)
        elif price_change > 1:
            momentum_score = weights.get('price_momentum', 15) * 0.7
        elif price_change > 0:
            momentum_score = weights.get('price_momentum', 15) * 0.4
        else:
            momentum_score = 0
        breakdown['momentum'] = f"{momentum_score:.1f}/15 ({price_change:+.1f}% move)"
        total_score += momentum_score
        
        # Volume Score (10 points) - Mock calculation
        volume_score = weights.get('volume_score', 10) * 0.8
        breakdown['volume'] = f"{volume_score:.1f}/10 (volume supporting)"
        total_score += volume_score
        
        # Trend Exhaustion Score (15 points) - Signs of reversal
        if rsi > 70 and price_change > 3:
            exhaustion_score = weights.get('trend_exhaustion', 15) * 0.9  # High exhaustion signals
        elif rsi > 65:
            exhaustion_score = weights.get('trend_exhaustion', 15) * 0.6
        else:
            exhaustion_score = weights.get('trend_exhaustion', 15) * 0.3
        breakdown['exhaustion'] = f"{exhaustion_score:.1f}/15 (exhaustion signals)"
        total_score += exhaustion_score
        
        # Bollinger Position (10 points) - Upper band proximity
        bb_score = weights.get('bollinger_position', 10) * 0.7
        breakdown['bollinger'] = f"{bb_score:.1f}/10 (BB upper band)"
        total_score += bb_score
        
        # MACD Score (5 points) - Divergence signals
        macd_score = weights.get('macd_score', 5) * 0.6
        breakdown['macd'] = f"{macd_score:.1f}/5 (MACD signals)"
        total_score += macd_score
        
        # Determine grade
        if total_score >= getattr(self.config, 'SCORE_EXCELLENT', 80):
            grade = "EXCELLENT"
        elif total_score >= getattr(self.config, 'SCORE_GOOD', 65):
            grade = "GOOD"
        elif total_score >= getattr(self.config, 'SCORE_FAIR', 50):
            grade = "FAIR"
        elif total_score >= getattr(self.config, 'SCORE_POOR', 35):
            grade = "POOR"
        else:
            grade = "AVOID"
        
        return {
            "score": round(total_score, 1),
            "breakdown": breakdown,
            "grade": grade
        }

    def _extract_wheel_signals(self, watchlist_result) -> dict:
        """Extract basic wheel strategy signals from watchlist data."""
        wheel_signals = {
            "good_put_candidates": [],
            "good_call_candidates": [], 
            "avoid_stocks": [],
            "summary": {}
        }
        
        if not self.config:
            return wheel_signals
            
        watchlist_stocks = watchlist_result.get("watchlist_stocks", {})
        
        put_candidates = []
        call_candidates = []
        
        for symbol, data in watchlist_stocks.items():
            if 'error' in data:
                continue
            
            rsi = data.get('rsi', 50)
            price_change = data.get('price_change_pct', 0)
            price = data.get('current_price', data.get('market_price', 0))
            
            # Simple put selling criteria (oversold conditions)
            if 25 <= rsi <= 50:  # Good RSI range for selling puts
                put_candidates.append({
                    "symbol": symbol,
                    "rsi": rsi,
                    "price": price,
                    "price_change": price_change,
                    "strategy": "cash_secured_put"
                })
            
            # Simple call selling criteria (overbought conditions)
            if 60 <= rsi <= 80:  # Good RSI range for selling calls
                call_candidates.append({
                    "symbol": symbol,
                    "rsi": rsi,
                    "price": price,
                    "price_change": price_change,
                    "strategy": "covered_call"
                })
            
            # Track stocks to avoid
            if (rsi < 25 or rsi > 80 or abs(price_change) > 10):
                wheel_signals["avoid_stocks"].append({
                    "symbol": symbol,
                    "rsi": rsi,
                    "price_change": price_change,
                    "reason": "too_volatile_or_extreme_rsi"
                })
        
        wheel_signals["good_put_candidates"] = put_candidates
        wheel_signals["good_call_candidates"] = call_candidates
        
        wheel_signals["summary"] = {
            "put_candidates": len(put_candidates),
            "call_candidates": len(call_candidates), 
            "avoid_count": len(wheel_signals["avoid_stocks"])
        }
        
        return wheel_signals

    def cleanup_old_data(self):
        """Clean up old watchlist analysis files based on config settings."""
        if not self.config:
            return
            
        cleanup_days = getattr(self.config, 'CLEANUP_OLD_DATA_DAYS', 30)
        
        try:
            from pathlib import Path
            import time
            
            cutoff_time = time.time() - (cleanup_days * 24 * 60 * 60)  # seconds
            
            # Find and remove old watchlist files
            pattern = "watchlist_*.json"
            old_files = []
            
            for filepath in self.out_dir.glob(pattern):
                if filepath.stat().st_mtime < cutoff_time:
                    old_files.append(filepath)
            
            if old_files:
                for filepath in old_files:
                    filepath.unlink()
                self.logger.info(f"🧹 Cleaned up {len(old_files)} old watchlist files (>{cleanup_days} days)")
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup old data: {e}")
    
    def _display_watchlist_summary(self, watchlist_result):
        """Display a summary of watchlist analysis with wheel strategy focus."""
        if not watchlist_result:
            return
            
        summary = watchlist_result.get("summary", {})
        total = summary.get("total_watchlist_analyzed", 0)
        successful = summary.get("successful_analyses", 0)
        failed = summary.get("failed_analyses", 0)
        
        self.logger.info(f"📊 Watchlist Analysis: {successful}/{total} successful")
        
        if failed > 0:
            self.logger.warning(f"⚠️  {failed} symbols failed analysis")
        
        # Show basic wheel strategy analysis
        wheel_signals = self._extract_wheel_signals(watchlist_result)
        wheel_summary = wheel_signals.get("summary", {})
        
        if any(wheel_summary.values()):
            self.logger.info("🎯 WHEEL STRATEGY OPPORTUNITIES:")
            if wheel_summary.get("put_candidates", 0) > 0:
                self.logger.info(f"   💰 Cash-Secured Puts: {wheel_summary['put_candidates']} candidates")
            
            if wheel_summary.get("call_candidates", 0) > 0:
                self.logger.info(f"   📞 Covered Calls: {wheel_summary['call_candidates']} candidates")
            
            if wheel_summary.get("avoid_count", 0) > 0:
                self.logger.info(f"   🚫 Avoid: {wheel_summary['avoid_count']} stocks (too volatile)")
        
        # Show top technical signals
        signals = summary.get("watchlist_signals", {})
        if signals:
            top_signals = sorted(signals.items(), key=lambda x: x[1], reverse=True)[:3]
            self.logger.info("🔝 Top technical signals:")
            for signal, count in top_signals:
                self.logger.info(f"   • {signal}: {count} stocks")
    
    def _check_live_trading_conditions(self, account_result, watchlist_result):
        """Check specific live trading conditions you want to monitor."""
        if not account_result and not watchlist_result:
            return
            
        # TODO: Add your specific monitoring logic here
        
        # Example checks you might want:
        # 1. Options expiring today
        # 2. Positions near stop losses  
        # 3. High volatility alerts
        # 4. Technical breakouts in watchlist
        # 5. Volume spike alerts
        
        # Check for interesting watchlist signals
        if watchlist_result:
            self._check_watchlist_alerts(watchlist_result)
        
        self.logger.info("✅ Live trading conditions checked")
    
    def _check_watchlist_alerts(self, watchlist_result):
        """Check for specific alerts in watchlist stocks using config thresholds."""
        watchlist_stocks = watchlist_result.get("watchlist_stocks", {})
        
        # Get thresholds from config
        if self.config:
            rsi_oversold = getattr(self.config, 'RSI_OVERSOLD_THRESHOLD', 30)
            rsi_overbought = getattr(self.config, 'RSI_OVERBOUGHT_THRESHOLD', 70)
            price_change_threshold = getattr(self.config, 'PRICE_CHANGE_ALERT_THRESHOLD', 3.0)
            max_alerts = getattr(self.config, 'MAX_ALERTS_DISPLAY', 5)
            enable_rsi = getattr(self.config, 'ENABLE_RSI_ALERTS', True)
            enable_price = getattr(self.config, 'ENABLE_PRICE_CHANGE_ALERTS', True)
        else:
            rsi_oversold, rsi_overbought = 30, 70
            price_change_threshold = 3.0
            max_alerts = 5
            enable_rsi = enable_price = True
        
        alerts = []
        
        for symbol, data in watchlist_stocks.items():
            if 'error' in data:
                continue
                
            # Check for RSI conditions
            if enable_rsi:
                rsi = data.get('rsi', 50)
                if rsi < rsi_oversold:
                    alerts.append(f"🔴 {symbol}: OVERSOLD (RSI: {rsi:.1f})")
                elif rsi > rsi_overbought:
                    alerts.append(f"🟢 {symbol}: OVERBOUGHT (RSI: {rsi:.1f})")
            
            # Check for significant price changes
            if enable_price:
                price_change = data.get('price_change_pct', 0)
                if abs(price_change) > price_change_threshold:
                    direction = "🚀" if price_change > 0 else "📉"
                    alerts.append(f"{direction} {symbol}: {price_change:+.1f}% price change")
        
        # Display alerts
        if alerts:
            self.logger.warning("🚨 WATCHLIST ALERTS:")
            for alert in alerts[:max_alerts]:
                self.logger.warning(f"   {alert}")
            if len(alerts) > max_alerts:
                self.logger.warning(f"   ... and {len(alerts) - max_alerts} more alerts")
        else:
            self.logger.debug("No watchlist alerts at this time")
    
    def _run_put_selection_analysis(self, account_result):
        """Run put selection analysis using the current account data."""
        try:
            from strategies.put_selection import PutSelectionEngine
            from datetime import datetime
            import json
            
            # Get account snapshot from the result
            account_snapshot = account_result.get('snapshot')
            if not account_snapshot:
                self.logger.warning("No account snapshot available for put selection")
                return None
            
            # Initialize put selection engine
            engine = PutSelectionEngine(self.client)
            
            # Generate timestamp for output files
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Define output paths
            raw_output_file = Path("data/option_search/puts/raw_recs") / f"put_recommendations_{timestamp}.json"
            final_output_file = Path("data/option_search/puts/final_recs") / f"top_puts_{timestamp}.json"
            
            # Ensure directories exist
            raw_output_file.parent.mkdir(parents=True, exist_ok=True)
            final_output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Run put selection analysis
            self.logger.info("🔍 Analyzing put opportunities...")
            put_analysis = engine.get_recommended_puts(account_snapshot)
            
            if not put_analysis:
                self.logger.info("No put recommendations generated")
                return None
            
            # Extract all recommended puts from the analysis result
            put_recommendations = []
            for symbol, data in put_analysis.items():
                if 'recommended_puts' in data:
                    put_recommendations.extend(data['recommended_puts'])
            
            # Save raw recommendations
            with open(raw_output_file, 'w') as f:
                json.dump(put_analysis, f, indent=2, default=str)
            
            # Filter and rank top puts (reuse logic from run_put_selection.py)
            top_puts = self._filter_and_rank_puts(put_recommendations)
            
            # Save final recommendations
            final_data = {
                "generated_at": datetime.now().isoformat(),
                "total_puts_analyzed": len(put_recommendations),
                "top_puts_count": len(top_puts),
                "top_puts": top_puts,
                "summary": {
                    "best_weekly_return": max([p.get('weekly_return_pct', 0) for p in top_puts]) if top_puts else 0,
                    "avg_weekly_return": sum([p.get('weekly_return_pct', 0) for p in top_puts]) / len(top_puts) if top_puts else 0,
                    "total_premium_available": sum([p.get('bid_price', 0) * p.get('multiplier', 100) for p in top_puts])
                }
            }
            
            with open(final_output_file, 'w') as f:
                json.dump(final_data, f, indent=2, default=str)
            
            self.logger.info(f"💾 Put analysis saved: {len(top_puts)} top recommendations")
            
            # Display summary
            if top_puts:
                self.logger.info("🎯 TOP PUT OPPORTUNITIES:")
                for i, put in enumerate(top_puts[:3], 1):  # Show top 3
                    symbol = put.get('symbol', put.get('underlying', 'N/A'))
                    strike = put.get('strike_price', put.get('strike', 0))
                    weekly_return = put.get('weekly_return_pct', 0)
                    bid = put.get('bid', put.get('bid_price', 0))
                    premium = put.get('total_premium_income', put.get('premium_received', 0))
                    self.logger.info(f"   {i}. {symbol} ${strike}P: {weekly_return:.2f}% weekly return (${bid:.2f} bid, ${premium} premium)")
            
            return {
                'raw_file': str(raw_output_file),
                'final_file': str(final_output_file),
                'put_count': len(put_recommendations),
                'top_put_count': len(top_puts)
            }
            
        except Exception as e:
            self.logger.error(f"Put selection analysis error: {e}")
            return None
    
    def _filter_and_rank_puts(self, put_recommendations):
        """Filter and rank puts using the same logic as run_put_selection.py"""
        if not put_recommendations:
            return []
        
        # Calculate composite scores for each put
        scored_puts = []
        for put in put_recommendations:
            try:
                # Calculate weekly return if not already present
                if 'weekly_return_pct' not in put:
                    annualized_return = put.get('annualized_return_pct', 0)
                    weekly_return = annualized_return / 52
                    put['weekly_return_pct'] = weekly_return
                else:
                    weekly_return = put.get('weekly_return_pct', 0)
                
                # Use existing composite score if available, otherwise calculate simplified version
                if 'composite_score' in put:
                    score = put['composite_score']
                else:
                    # Calculate composite score (simplified version)
                    score = 0
                    
                    # Return score (40% weight)
                    if weekly_return >= 2.0:
                        score += 40
                    elif weekly_return >= 1.5:
                        score += 30
                    elif weekly_return >= 1.0:
                        score += 20
                    else:
                        score += max(0, weekly_return * 10)
                    
                    put['composite_score'] = score
                
                scored_puts.append(put)
                
            except Exception as e:
                self.logger.debug(f"Error scoring put {put.get('symbol', 'Unknown')}: {e}")
                continue
        
        # Sort by composite score (highest first)
        scored_puts.sort(key=lambda x: x.get('composite_score', 0), reverse=True)
        
        # Return top 10
        return scored_puts[:10]
    
    def cleanup_old_data(self):
        """Clean up old data files, keeping only the last 10 files per directory."""
        import glob
        
        # Directories to clean up
        cleanup_dirs = [
            "data/stock_watchlist",
            "data/stock_ranking", 
            "data/account",
            "data/option_search/puts/raw_recs",
            "data/option_search/puts/final_recs"
        ]
        
        self.logger.info("🧹 Cleaning up old data files...")
        total_cleaned = 0
        
        for dir_path in cleanup_dirs:
            try:
                full_path = Path(dir_path)
                if not full_path.exists():
                    continue
                
                # Get all JSON files in the directory
                json_files = list(full_path.glob("*.json"))
                
                # Skip account_snapshot.json (always keep the current one)
                json_files = [f for f in json_files if f.name != "account_snapshot.json"]
                
                if len(json_files) <= 10:
                    continue  # Nothing to clean up
                
                # Sort by modification time (newest first)
                json_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
                
                # Keep the 10 newest, delete the rest
                files_to_delete = json_files[10:]
                
                for file_path in files_to_delete:
                    try:
                        file_path.unlink()
                        total_cleaned += 1
                        self.logger.debug(f"   Deleted: {file_path.name}")
                    except Exception as e:
                        self.logger.warning(f"   Failed to delete {file_path.name}: {e}")
                
                if files_to_delete:
                    self.logger.info(f"   📁 {dir_path}: Cleaned {len(files_to_delete)} old files (kept 10 newest)")
                    
            except Exception as e:
                self.logger.warning(f"   Failed to clean {dir_path}: {e}")
        
        if total_cleaned > 0:
            self.logger.info(f"✅ Cleanup complete: Removed {total_cleaned} old files")
        else:
            self.logger.debug("No files needed cleanup")
    
    def run(self, duration_minutes: float = None):
        """Run the live monitor."""
        self.running = True
        start_time = datetime.now()
        iteration = 0
        
        self.logger.info(f"🚀 Starting live trading monitor (every {self.interval}s)")
        if duration_minutes:
            self.logger.info(f"⏱️  Will run for {duration_minutes} minutes")
        
        # Cleanup old data files at startup
        self.cleanup_old_data()
        
        try:
            while self.running:
                iteration += 1
                
                # Check if we should stop based on duration
                if duration_minutes:
                    elapsed = (datetime.now() - start_time).total_seconds() / 60
                    if elapsed >= duration_minutes:
                        self.logger.info(f"⏰ Reached {duration_minutes} minute limit")
                        break
                
                # Check market hours (unless forced to run)
                if not self.force_run and not self.is_market_hours():
                    self.logger.info("📴 Market closed - skipping monitoring (use --force to override)")
                    time.sleep(self.interval)
                    continue
                
                self.logger.info(f"\n📊 === ITERATION {iteration} ===")
                result = self.run_monitoring_cycle()
                
                if result and result.get('account'):
                    account_value = result['account'].get('total_account_value', 0)
                    self.logger.info(f"💰 Account Value: ${account_value:,.2f}")
                    
                    # Show watchlist summary
                    if result.get('watchlist'):
                        watchlist_summary = result['watchlist'].get('summary', {})
                        watchlist_count = watchlist_summary.get('successful_analyses', 0)
                        self.logger.info(f"📋 Watchlist: {watchlist_count} stocks analyzed")
                
                # Wait for next iteration
                if self.running:  # Check if we're still running
                    self.logger.info(f"⏸️  Waiting {self.interval} seconds...")
                    time.sleep(self.interval)
                    
        except KeyboardInterrupt:
            self.logger.info("\n🛑 Stopping live monitor...")
        except Exception as e:
            self.logger.error(f"Live monitor error: {e}")
        finally:
            self.running = False
            
            # Cleanup old data files when stopping
            self.cleanup_old_data()
            
            elapsed = (datetime.now() - start_time).total_seconds() / 60
            self.logger.info(f"✅ Live monitor stopped after {elapsed:.1f} minutes ({iteration} iterations)")

    def _generate_wheel_rankings(self, analysis_data: dict) -> dict:
        """Generate wheel strategy rankings from watchlist analysis data."""
        try:
            # Import the ranking system components
            from scripts.rank_wheel_candidates import WheelRanker
            
            # Create a ranker instance
            ranker = WheelRanker()
            
            # Generate rankings from the analysis data
            rankings = ranker.rank_wheel_candidates(analysis_data)
            
            return rankings
            
        except Exception as e:
            self.logger.error(f"Error generating rankings: {e}")
            return None
    
    def _save_wheel_rankings(self, rankings: dict, timestamp: str):
        """Save wheel rankings to the ranking directory."""
        try:
            # Use dedicated ranking directory
            ranking_dir = getattr(self.config, 'RANKING_OUTPUT_DIR', 'data/stock_ranking')
            ranking_path = Path(ranking_dir)
            ranking_path.mkdir(parents=True, exist_ok=True)
            
            filename = f"wheel_rankings_{timestamp}.json"
            filepath = ranking_path / filename
            
            safe_write_json(filepath, rankings)
            self.logger.info(f"💾 Saved wheel rankings: {filename}")
            
        except Exception as e:
            self.logger.error(f"Failed to save wheel rankings: {e}")
    
    def _display_live_rankings(self, rankings: dict):
        """Display condensed rankings in live monitor format."""
        if not rankings:
            return
        
        summary = rankings.get('summary', {})
        put_candidates = rankings.get('put_candidates', [])
        call_candidates = rankings.get('call_candidates', [])
        
        if not put_candidates and not call_candidates:
            return
        
        self.logger.info("🏆 LIVE WHEEL RANKINGS:")
        
        # Show top 3 put candidates
        if put_candidates:
            self.logger.info(f"   💰 Top Puts ({len(put_candidates)} total):")
            for i, candidate in enumerate(put_candidates[:3], 1):
                grade_emoji = {"EXCELLENT": "🟢", "GOOD": "🟡", "FAIR": "🟠", "POOR": "🔴"}.get(candidate['grade'], "⚪")
                self.logger.info(
                    f"      {i}. {candidate['symbol']}: {candidate['score']:.1f}/100 {grade_emoji}{candidate['grade']} "
                    f"(RSI: {candidate['rsi']:.1f}, ${candidate['price']:.2f})"
                )
        
        # Show top 3 call candidates  
        if call_candidates:
            self.logger.info(f"   📞 Top Calls ({len(call_candidates)} total):")
            for i, candidate in enumerate(call_candidates[:3], 1):
                grade_emoji = {"EXCELLENT": "🟢", "GOOD": "🟡", "FAIR": "🟠", "POOR": "🔴"}.get(candidate['grade'], "⚪")
                self.logger.info(
                    f"      {i}. {candidate['symbol']}: {candidate['score']:.1f}/100 {grade_emoji}{candidate['grade']} "
                    f"(RSI: {candidate['rsi']:.1f}, ${candidate['price']:.2f})"
                )
        
        # Show best scores
        top_put_score = summary.get('top_put_score', 0)
        top_call_score = summary.get('top_call_score', 0)
        if top_put_score > 0 or top_call_score > 0:
            self.logger.info(f"   📊 Best Scores: Puts {top_put_score:.1f}/100, Calls {top_call_score:.1f}/100")


def main():
    """Main entry point for live monitor."""
    parser = argparse.ArgumentParser(description="Live trading monitor")
    parser.add_argument("--duration", type=float, help="Duration in minutes (default: run indefinitely)")
    parser.add_argument("--interval", type=int, default=20, help="Interval in seconds (default: 20)")
    parser.add_argument("--out", default="data/account", help="Output directory")
    parser.add_argument("--config", default="config/settings.py", help="Path to configuration file")
    parser.add_argument("--simulate", action="store_true", help="Use simulated data")
    parser.add_argument("--force", action="store_true", help="Force run regardless of market hours")
    args = parser.parse_args()
    
    # Initialize client (reuse main.py logic)
    if args.simulate:
        client = SimBrokerClient()
    else:
        config = SchwabConfig.from_env()
        token_file = Path(config.token_path)
        if token_file.exists() and not config.is_valid():
            config.app_key = "ER0kVS2P0U9WMMlRRt7Mw4ELCmVRwTB5"
            config.app_secret = "3mJejG1MBpISgcjj"
        
        client = RealBrokerClient(
            app_key=config.app_key,
            app_secret=config.app_secret,
            redirect_uri=config.redirect_uri,
            token_path=config.token_path
        )
    
    # Start monitoring
    monitor = LiveTradingMonitor(client, Path(args.out), args.interval, args.config, force_run=args.force)
    monitor.run(duration_minutes=args.duration)


if __name__ == "__main__":
    main()