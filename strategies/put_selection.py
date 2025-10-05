"""Cash Secured Put Selection Engine.

This module provides functionality for analyzing and selecting optimal cash secured put options.
It integrates with existing account data and wheel rankings to provide intelligent put selection:
- Uses account_snapshot.json for current portfolio allocations
- Leverages wheel_rankings to adjust aggressiveness based on stock quality
- Only analyzes stocks with <20% current allocation to maintain diversification
- Applies grade-based criteria (EXCELLENT = aggressive, GOOD = moderate, etc.)
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
import logging
import json
from pathlib import Path
import glob

try:
    # Try relative imports first (when run as module from parent)
    from ..core.models import AccountSnapshot
    from ..utils.logging import get_logger
except ImportError:
    # Fall back to direct imports (when run from within directory)
    from core.models import AccountSnapshot
    from utils.logging import get_logger


class PutSelectionEngine:
    """Engine for selecting optimal cash secured put options."""
    
    def __init__(self, client, data_dir: str = "data", max_total_allocation_pct: float = 20.0):
        """Initialize the put selection engine.
        
        Args:
            client: Broker client for market data
            data_dir: Directory containing account and ranking data
            max_total_allocation_pct: Maximum total allocation per symbol (stock + puts)
        """
        self.client = client
        self.data_dir = Path(data_dir)
        self.max_total_allocation_pct = max_total_allocation_pct
        self.logger = get_logger()
        
        # Grade-based criteria for weekly put selection (based on technical analysis data)
        self.grade_criteria = {
            'EXCELLENT': {
                # Technical profile: Strong uptrend, RSI 30-70, bullish EMA alignment, above support
                'min_annualized_return': 15.0,   # Lower return needed for quality stocks
                'min_downside_protection': 1.5,  # Minimal protection needed - strong stocks
                'max_assignment_prob': 60.0,     # Higher tolerance - we want to own excellent stocks
                'preferred_dte_range': (1, 10),  # Weekly focus
                'max_rsi': 75.0,                 # Avoid extremely overbought
                'min_rsi': 25.0,                 # Avoid extremely oversold
                'required_signals': ['EMA BULLISH ALIGNMENT', 'ABOVE LONG-TERM EMA'],  # Strong trend
                'volume_ratio_min': 0.3,         # Decent liquidity
                'max_bid_ask_spread_pct': 15.0,  # Max 15% bid-ask spread for decent liquidity
                'min_open_interest': 10,         # Minimum open interest for assignment likelihood
                'bollinger_position': 'any',     # Can be anywhere in Bollinger bands
                'aggressiveness_multiplier': 1.4
            },
            'GOOD': {
                # Technical profile: Decent trend, RSI reasonable, some bullish signals
                'min_annualized_return': 25.0,   # Moderate return requirement
                'min_downside_protection': 2.5,  
                'max_assignment_prob': 50.0,     
                'preferred_dte_range': (1, 10),  
                'max_rsi': 80.0,                 # Slightly more overbought tolerance
                'min_rsi': 20.0,                 # Slightly more oversold tolerance
                'required_signals': ['ABOVE LONG-TERM EMA'],  # At least above long-term trend
                'volume_ratio_min': 0.4,         # Good liquidity
                'max_bid_ask_spread_pct': 12.0,  # Max 12% bid-ask spread for good liquidity
                'min_open_interest': 25,         # Higher open interest requirement
                'bollinger_position': 'any',
                'aggressiveness_multiplier': 1.1
            },
            'FAIR': {
                # Technical profile: Mixed signals, sideways or weak trend
                'min_annualized_return': 35.0,   # Higher return for uncertain quality
                'min_downside_protection': 4.0,  
                'max_assignment_prob': 40.0,     
                'preferred_dte_range': (1, 7),   # Shorter duration for safety
                'max_rsi': 85.0,                 # More tolerance for fair stocks
                'min_rsi': 15.0,                 
                'required_signals': [],          # No specific signal requirements
                'volume_ratio_min': 0.5,         # Need good liquidity for exit
                'max_bid_ask_spread_pct': 10.0,  # Max 10% bid-ask spread for fair stocks
                'min_open_interest': 50,         # Need decent open interest
                'bollinger_position': 'any',
                'aggressiveness_multiplier': 0.9
            },
            'POOR': {
                # Technical profile: Bearish signals, downtrend, poor fundamentals
                'min_annualized_return': 50.0,   # Very high return for poor quality
                'min_downside_protection': 6.0,  # Need significant protection
                'max_assignment_prob': 25.0,     # Low assignment tolerance
                'preferred_dte_range': (1, 5),   # Very short duration only
                'max_rsi': 90.0,                 # Any RSI level (desperate plays)
                'min_rsi': 10.0,                 
                'required_signals': [],          # No requirements - just price
                'volume_ratio_min': 0.6,         # Need high liquidity for quick exits
                'max_bid_ask_spread_pct': 8.0,   # Max 8% bid-ask spread for poor stocks (need exit)
                'min_open_interest': 100,        # Need high open interest for poor stocks
                'bollinger_position': 'any',
                'aggressiveness_multiplier': 0.6
            }
        }
    
    def _load_account_allocations(self) -> Dict[str, Dict]:
        """Load current stock allocations from account snapshot.
        
        Returns:
            Dictionary of stock allocations
        """
        try:
            snapshot_file = self.data_dir / "account" / "account_snapshot.json"
            if not snapshot_file.exists():
                self.logger.warning(f"Account snapshot not found: {snapshot_file}")
                return {}
            
            with open(snapshot_file, 'r') as f:
                data = json.load(f)
            
            return data.get('stock_allocations', {})
            
        except Exception as e:
            self.logger.error(f"Error loading account allocations: {e}")
            return {}
    
    def _load_technical_data(self) -> Dict[str, Dict]:
        """Load technical analysis data from account snapshot.
        
        Returns:
            Dictionary of technical data by symbol
        """
        try:
            snapshot_file = self.data_dir / "account" / "account_snapshot.json"
            if not snapshot_file.exists():
                return {}
            
            with open(snapshot_file, 'r') as f:
                data = json.load(f)
            
            return data.get('technicals', {}).get('stocks', {})
            
        except Exception as e:
            self.logger.error(f"Error loading technical data: {e}")
            return {}
    
    def _load_current_option_positions(self) -> Dict[str, List[Dict]]:
        """Load current option positions from account snapshot.
        
        Returns:
            Dictionary of option positions by symbol
        """
        try:
            snapshot_file = self.data_dir / "account" / "account_snapshot.json"
            if not snapshot_file.exists():
                return {}
            
            with open(snapshot_file, 'r') as f:
                data = json.load(f)
            
            options = data.get('options', [])
            positions_by_symbol = {}
            
            for option in options:
                symbol = option.get('symbol')
                if symbol:
                    if symbol not in positions_by_symbol:
                        positions_by_symbol[symbol] = []
                    positions_by_symbol[symbol].append(option)
            
            return positions_by_symbol
            
        except Exception as e:
            self.logger.error(f"Error loading current option positions: {e}")
            return {}
    
    def _load_latest_wheel_rankings(self) -> Dict[str, Dict]:
        """Load the latest wheel rankings.
        
        Returns:
            Dictionary of wheel rankings by symbol
        """
        try:
            rankings_dir = self.data_dir / "stock_ranking"
            if not rankings_dir.exists():
                self.logger.warning(f"Rankings directory not found: {rankings_dir}")
                return {}
            
            # Find the latest wheel rankings file
            pattern = str(rankings_dir / "wheel_rankings_*.json")
            ranking_files = glob.glob(pattern)
            
            if not ranking_files:
                self.logger.warning("No wheel ranking files found")
                return {}
            
            # Get the most recent file
            latest_file = max(ranking_files, key=lambda x: Path(x).stat().st_mtime)
            self.logger.info(f"Loading wheel rankings from: {Path(latest_file).name}")
            
            with open(latest_file, 'r') as f:
                data = json.load(f)
            
            # Convert to symbol-keyed dictionary
            rankings = {}
            
            # Handle both old and new formats
            candidates = data.get('put_candidates', data.get('rankings', []))
            for item in candidates:
                symbol = item.get('symbol')
                if symbol:
                    # Normalize the data structure
                    rankings[symbol] = {
                        'overall_grade': item.get('grade', item.get('overall_grade')),
                        'final_score': item.get('score', item.get('final_score')),
                        'strategy': item.get('strategy'),
                        'breakdown': item.get('breakdown', {}),
                        'rsi': item.get('rsi'),
                        'price': item.get('price'),
                        'price_change': item.get('price_change')
                    }
            
            return rankings
            
        except Exception as e:
            self.logger.error(f"Error loading wheel rankings: {e}")
            return {}
    
    def _validate_technical_criteria(self, symbol: str, grade: str, technical_data: Dict) -> bool:
        """Validate if symbol meets technical criteria for its grade.
        
        Args:
            symbol: Stock symbol
            grade: Stock grade (EXCELLENT, GOOD, FAIR, POOR)
            technical_data: Technical analysis data for the symbol
            
        Returns:
            True if meets technical criteria, False otherwise
        """
        criteria = self.grade_criteria.get(grade, {})
        if not criteria or not technical_data:
            return True  # Default to allow if no criteria or data
        
        try:
            indicators = technical_data.get('technical_indicators', {})
            signals = technical_data.get('signals', [])
            
            # Check RSI bounds
            rsi = indicators.get('rsi')
            if rsi is not None:
                if rsi > criteria.get('max_rsi', 100) or rsi < criteria.get('min_rsi', 0):
                    self.logger.debug(f"{symbol}: RSI {rsi:.1f} outside bounds [{criteria.get('min_rsi', 0)}-{criteria.get('max_rsi', 100)}]")
                    return False
            
            # Check required signals
            required_signals = criteria.get('required_signals', [])
            for required_signal in required_signals:
                if not any(required_signal in signal for signal in signals):
                    self.logger.debug(f"{symbol}: Missing required signal: {required_signal}")
                    return False
            
            # Check volume ratio
            volume_ratio = indicators.get('volume_ratio')
            min_volume = criteria.get('volume_ratio_min', 0)
            if volume_ratio is not None and volume_ratio < min_volume:
                self.logger.debug(f"{symbol}: Volume ratio {volume_ratio:.2f} < {min_volume}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.warning(f"Error validating technical criteria for {symbol}: {e}")
            return True  # Default to allow on error
    
    def _get_eligible_symbols(self) -> List[Tuple[str, str, float]]:
        """Get symbols eligible for put analysis based on allocations, technical criteria, and existing positions.
        
        Returns:
            List of tuples: (symbol, grade, current_allocation_pct)
        """
        allocations = self._load_account_allocations()
        rankings = self._load_latest_wheel_rankings()
        technical_data = self._load_technical_data()
        current_options = self._load_current_option_positions()
        
        eligible = []
        
        for symbol, ranking_data in rankings.items():
            # Skip symbols with existing option positions
            if symbol in current_options:
                positions = current_options[symbol]
                position_summary = []
                for pos in positions:
                    qty = pos.get('qty', 0)
                    put_call = pos.get('put_call', 'UNKNOWN')
                    strike = pos.get('strike', 'N/A')
                    expiry = pos.get('expiry', 'N/A')[:10] if pos.get('expiry') else 'N/A'
                    position_summary.append(f"{qty} {put_call} ${strike} exp {expiry}")
                
                self.logger.debug(f"Skipping {symbol}: existing option positions [{', '.join(position_summary)}]")
                continue
            
            # Get current allocation percentage
            current_allocation = float(allocations.get(symbol, {}).get('total_allocation_pct', '0'))
            
            # Only consider symbols with <20% allocation
            if current_allocation >= self.max_total_allocation_pct:
                self.logger.debug(f"Skipping {symbol}: allocation {current_allocation:.1f}% >= {self.max_total_allocation_pct}%")
                continue
            
            grade = ranking_data.get('overall_grade', 'UNKNOWN')
            if grade not in self.grade_criteria:
                continue
            
            # Validate technical criteria for this grade
            symbol_technical = technical_data.get(symbol, {})
            if not self._validate_technical_criteria(symbol, grade, symbol_technical):
                self.logger.debug(f"Skipping {symbol}: failed technical criteria for {grade} grade")
                continue
            
            eligible.append((symbol, grade, current_allocation))
            self.logger.debug(f"Eligible: {symbol} ({grade}, {current_allocation:.1f}% allocated)")
        
        # Sort by grade quality and current allocation (prefer better grades, lower allocation)
        grade_priority = {'EXCELLENT': 0, 'GOOD': 1, 'FAIR': 2, 'POOR': 3}
        eligible.sort(key=lambda x: (grade_priority.get(x[1], 99), x[2]))
        
        return eligible
    
    def analyze_put_opportunities(self, account_value: Decimal) -> Dict[str, Any]:
        """Analyze cash secured put opportunities using account data and wheel rankings.
        
        Args:
            account_value: Total account value for position sizing
            
        Returns:
            Dictionary with put analysis for eligible symbols
        """
        # Get eligible symbols from data files
        eligible_symbols = self._get_eligible_symbols()
        
        if not eligible_symbols:
            self.logger.warning("No eligible symbols found for put analysis")
            return {}
        
        self.logger.info(f"Analyzing cash secured put opportunities for {len(eligible_symbols)} eligible symbols")
        
        opportunities = {}
        
        for symbol, grade, current_allocation_pct in eligible_symbols:
            try:
                self.logger.debug(f"Analyzing puts for {symbol} (Grade: {grade}, Allocation: {current_allocation_pct:.1f}%)")
                
                # Get current stock price and technical data
                stock_data = self._get_stock_data(symbol)
                if not stock_data:
                    continue
                
                # Get options chain for puts
                options_data = self._get_put_options_chain(symbol)
                if not options_data:
                    continue
                
                # Calculate position sizing based on remaining allocation capacity
                remaining_allocation_pct = self.max_total_allocation_pct - current_allocation_pct
                max_position_value = account_value * Decimal(str(remaining_allocation_pct / 100))
                
                # Get grade-specific criteria
                criteria = self.grade_criteria[grade]
                
                # Analyze put strikes and expirations with grade-based criteria
                put_analysis = self._analyze_put_strikes_with_criteria(
                    symbol, grade, stock_data, options_data, 
                    max_position_value, current_allocation_pct, criteria
                )
                
                opportunities[symbol] = {
                    'symbol': symbol,
                    'grade': grade,
                    'stock_data': stock_data,
                    'current_allocation_pct': current_allocation_pct,
                    'remaining_allocation_pct': remaining_allocation_pct,
                    'max_position_value': str(max_position_value),
                    'criteria': criteria,
                    'put_opportunities': put_analysis,
                    'analysis_timestamp': datetime.now().isoformat()
                }
                
            except Exception as e:
                self.logger.error(f"Error analyzing puts for {symbol}: {e}")
                opportunities[symbol] = {
                    'symbol': symbol,
                    'grade': grade if 'grade' in locals() else 'UNKNOWN',
                    'error': str(e),
                    'analysis_timestamp': datetime.now().isoformat()
                }
        
        return opportunities
    
    def _get_stock_data(self, symbol: str) -> Optional[Dict]:
        """Get current stock price and basic data.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dictionary with stock data or None if failed
        """
        try:
            # Access the raw schwab client if available
            raw_client = getattr(self.client, 'client', None) if self.client else None
            if not raw_client:
                self.logger.warning(f"No raw client available for {symbol}")
                return None
            
            # Get current price from quote or price history
            end_date = datetime.now()
            start_date = end_date - timedelta(days=5)
            
            price_history = raw_client.price_history(
                symbol=symbol,
                periodType='day',
                period=5,
                frequencyType='minute',
                frequency=1,
                startDate=start_date,
                endDate=end_date
            )
            
            if price_history.status_code != 200:
                self.logger.warning(f"Failed to get price data for {symbol}: {price_history.status_code}")
                return None
            
            candles = price_history.json().get('candles', [])
            if not candles:
                return None
            
            latest_candle = candles[-1]
            current_price = latest_candle['close']
            
            return {
                'current_price': current_price,
                'high_52w': max([c['high'] for c in candles]),  # Approximate from recent data
                'low_52w': min([c['low'] for c in candles]),   # Approximate from recent data
                'volume': latest_candle['volume'],
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting stock data for {symbol}: {e}")
            return None
    
    def _get_put_options_chain(self, symbol: str) -> Optional[Dict]:
        """Get put options chain for the symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Put options chain data or None if failed
        """
        try:
            # Access the raw schwab client if available
            raw_client = getattr(self.client, 'client', None) if self.client else None
            if not raw_client:
                self.logger.warning(f"No raw client available for options chain {symbol}")
                return None
            
            # Get options chain - API doesn't accept fromDate/toDate, use contractType only
            # This will return all available puts (typically up to 30-60 days)
            options_chain = raw_client.option_chains(
                symbol=symbol,
                contractType='PUT'
            )
            
            if options_chain.status_code != 200:
                self.logger.warning(f"Failed to get options chain for {symbol}: {options_chain.status_code}")
                return None
            
            return options_chain.json()
            
        except Exception as e:
            self.logger.error(f"Error getting options chain for {symbol}: {e}")
            return None
    
    def _analyze_put_strikes_with_criteria(self, symbol: str, grade: str, stock_data: Dict, 
                                          options_data: Dict, max_position_value: Decimal, 
                                          current_allocation_pct: float, criteria: Dict) -> List[Dict]:
        """Analyze put strike prices using grade-based criteria.
        
        Args:
            symbol: Stock symbol
            grade: Stock grade (EXCELLENT, GOOD, FAIR, POOR)
            stock_data: Current stock price and data
            options_data: Options chain data
            max_position_value: Maximum position value allowed
            current_allocation_pct: Current allocation percentage for this symbol
            criteria: Grade-specific selection criteria
            
        Returns:
            List of put opportunities sorted by attractiveness
        """
        opportunities = []
        current_price = stock_data['current_price']
        
        # Get put expiration dates map
        put_exp_map = options_data.get('putExpDateMap', {})
        
        # Extract criteria
        min_dte, max_dte = criteria['preferred_dte_range']
        aggressiveness = criteria['aggressiveness_multiplier']
        
        for exp_date_str, strikes_data in put_exp_map.items():
            # Parse expiration date
            exp_date = datetime.strptime(exp_date_str.split(':')[0], '%Y-%m-%d').date()
            days_to_expiry = (exp_date - datetime.now().date()).days
            
            # Use grade-specific DTE range
            if days_to_expiry < min_dte or days_to_expiry > max_dte:
                continue
            
            for strike_str, option_list in strikes_data.items():
                if not option_list:
                    continue
                
                option = option_list[0]  # First option at this strike
                strike_price = float(strike_str)
                
                # Adjust strike selection for weekly wheeling strategy
                # Weekly options allow for more aggressive strikes since we're looking for higher premiums
                max_strike_ratio = 0.96 + (aggressiveness - 1.0) * 0.08  # More aggressive range for weekly options
                max_strike_ratio = max(0.85, min(1.05, max_strike_ratio))  # Wider bounds for weekly options
                
                # For weekly wheeling, we can be more aggressive with strikes
                # We want decent premium and are okay with assignment
                if strike_price >= current_price * max_strike_ratio:
                    continue
                
                # Calculate metrics for this put
                metrics = self._calculate_put_metrics_with_criteria(
                    symbol, grade, current_price, strike_price, option, 
                    days_to_expiry, max_position_value, current_allocation_pct, criteria
                )
                
                if metrics:
                    opportunities.append(metrics)
        
        # Sort by attractiveness score (higher is better)
        opportunities.sort(key=lambda x: x.get('attractiveness_score', 0), reverse=True)
        
        # Return more opportunities for better grades
        max_opportunities = {
            'EXCELLENT': 15,
            'GOOD': 10, 
            'FAIR': 8,
            'POOR': 5
        }.get(grade, 10)
        
        return opportunities[:max_opportunities]
    
    def _calculate_put_metrics_with_criteria(self, symbol: str, grade: str, current_price: float, 
                                            strike_price: float, option_data: Dict, days_to_expiry: int, 
                                            max_position_value: Decimal, current_allocation_pct: float,
                                            criteria: Dict) -> Optional[Dict]:
        """Calculate key metrics for a cash secured put opportunity using grade-based criteria.
        
        Args:
            symbol: Stock symbol
            grade: Stock grade (EXCELLENT, GOOD, FAIR, POOR)
            current_price: Current stock price
            strike_price: Put strike price
            option_data: Option chain data for this strike
            days_to_expiry: Days until expiration
            max_position_value: Maximum position value allowed
            current_allocation_pct: Current allocation for this symbol
            criteria: Grade-specific selection criteria
            
        Returns:
            Dictionary with put metrics or None if not viable
        """
        try:
            # Extract option data
            bid = option_data.get('bid', 0)
            ask = option_data.get('ask', 0)
            mark = option_data.get('mark', 0)
            open_interest = option_data.get('openInterest', 0)
            
            # Check bid-ask spread filtering
            if bid > 0 and ask > 0:
                spread_pct = ((ask - bid) / ((ask + bid) / 2)) * 100
                max_spread = criteria.get('max_bid_ask_spread_pct', 20.0)  # Default 20%
                if spread_pct > max_spread:
                    self.logger.debug(f"Skipping {symbol} ${strike_price} PUT: bid-ask spread {spread_pct:.1f}% > {max_spread}%")
                    return None
            
            # Check minimum open interest requirement
            min_oi = criteria.get('min_open_interest', 0)
            if open_interest < min_oi:
                self.logger.debug(f"Skipping {symbol} ${strike_price} PUT: open interest {open_interest} < {min_oi}")
                return None
            
            # Use mark price, fallback to mid-point of bid/ask
            premium = mark if mark > 0 else (bid + ask) / 2
            if premium <= 0:
                return None
            
            # Calculate key metrics
            collateral_required = strike_price * 100  # Per contract
            premium_received = premium * 100  # Per contract
            
            # Calculate how many contracts we can afford
            max_contracts = int(max_position_value / Decimal(str(collateral_required)))
            if max_contracts < 1:
                return None
            
            # Return calculations
            annualized_return = (premium / strike_price) * (365 / days_to_expiry) * 100
            downside_protection = ((current_price - strike_price) / current_price) * 100
            break_even_price = strike_price - premium
            assignment_probability = self._estimate_assignment_probability(
                current_price, strike_price, days_to_expiry
            )
            
            # Apply grade-based filtering
            if not self._meets_grade_criteria(annualized_return, downside_protection, 
                                            assignment_probability, criteria):
                return None
            
            # Calculate attractiveness score (0-100) with grade-based and technical adjustments
            attractiveness_score = self._calculate_attractiveness_score_with_grade(
                symbol, annualized_return, downside_protection, days_to_expiry, 
                assignment_probability, current_allocation_pct, grade, criteria
            )
            
            # Calculate bid-ask spread percentage for output
            bid_ask_spread_pct = 0
            if bid > 0 and ask > 0:
                bid_ask_spread_pct = ((ask - bid) / ((ask + bid) / 2)) * 100
            
            return {
                'symbol': symbol,
                'grade': grade,
                'strike_price': strike_price,
                'premium': premium,
                'bid': bid,
                'ask': ask,
                'mark': mark,
                'bid_ask_spread_pct': round(bid_ask_spread_pct, 1),
                'days_to_expiry': days_to_expiry,
                'expiration_date': option_data.get('expirationDate', ''),
                'collateral_required': collateral_required,
                'premium_received': premium_received,
                'max_contracts': max_contracts,
                'total_premium_income': premium_received * max_contracts,
                'total_collateral': collateral_required * max_contracts,
                'annualized_return_pct': round(annualized_return, 2),
                'downside_protection_pct': round(downside_protection, 2),
                'break_even_price': round(break_even_price, 2),
                'assignment_probability_pct': round(assignment_probability, 1),
                'attractiveness_score': round(attractiveness_score, 1),
                'open_interest': option_data.get('openInterest', 0),
                'volume': option_data.get('totalVolume', 0),
                'delta': option_data.get('delta', 0),
                'theta': option_data.get('theta', 0),
                'implied_volatility': option_data.get('volatility', 0),
                'criteria_applied': criteria
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating put metrics for {symbol} {strike_price}: {e}")
            return None
    
    def _meets_grade_criteria(self, annualized_return: float, downside_protection: float,
                             assignment_probability: float, criteria: Dict) -> bool:
        """Check if put opportunity meets grade-based minimum criteria.
        
        Args:
            annualized_return: Annualized return percentage
            downside_protection: Downside protection percentage
            assignment_probability: Assignment probability percentage
            criteria: Grade-specific criteria
            
        Returns:
            True if meets criteria, False otherwise
        """
        return (annualized_return >= criteria['min_annualized_return'] and
                downside_protection >= criteria['min_downside_protection'] and
                assignment_probability <= criteria['max_assignment_prob'])
    
    def _estimate_assignment_probability(self, current_price: float, strike_price: float,
                                       days_to_expiry: int) -> float:
        """Estimate probability of assignment for weekly options (rough approximation).
        
        Args:
            current_price: Current stock price
            strike_price: Put strike price
            days_to_expiry: Days until expiration
            
        Returns:
            Estimated assignment probability (0-100)
        """
        # Model optimized for weekly options (higher volatility, shorter time)
        moneyness = strike_price / current_price
        
        if moneyness < 0.85:  # Far OTM
            base_prob = 8   # Slightly higher for weekly options
        elif moneyness < 0.92:  # OTM
            base_prob = 20  # Higher probability due to weekly volatility
        elif moneyness < 0.98:  # Near OTM
            base_prob = 35
        elif moneyness < 1.02:  # Near ATM  
            base_prob = 50  # Higher for weekly options
        else:  # ITM
            base_prob = 80
        
        # Time decay is more aggressive for weekly options
        if days_to_expiry <= 3:
            time_factor = 1.2  # Higher probability for very short expiry
        elif days_to_expiry <= 7:
            time_factor = 1.0  # Standard for weekly
        else:
            time_factor = max(0.4, days_to_expiry / 10)  # Reduced factor for longer expiry
        
        return min(95, base_prob * time_factor)
    
    def _calculate_attractiveness_score_with_grade(self, symbol: str, annualized_return: float, 
                                                  downside_protection: float, days_to_expiry: int, 
                                                  assignment_prob: float, current_allocation_pct: float, 
                                                  grade: str, criteria: Dict) -> float:
        """Calculate overall attractiveness score with grade-based and technical adjustments.
        
        Args:
            symbol: Stock symbol
            annualized_return: Annualized return percentage
            downside_protection: Downside protection percentage
            days_to_expiry: Days until expiration
            assignment_prob: Assignment probability
            current_allocation_pct: Current allocation for this symbol
            grade: Stock grade (EXCELLENT, GOOD, FAIR, POOR)
            criteria: Grade-specific criteria
            
        Returns:
            Attractiveness score (0-100)
        """
        aggressiveness = criteria['aggressiveness_multiplier']
        preferred_dte_min, preferred_dte_max = criteria['preferred_dte_range']
        
        # Base score from return (max 35 points), adjusted for grade
        # Better grades get bonus points for meeting return thresholds
        excess_return = max(0, annualized_return - criteria['min_annualized_return'])
        return_score = min(35, (annualized_return * 1.2) + (excess_return * aggressiveness))
        
        # Downside protection score (max 20 points)
        excess_protection = max(0, downside_protection - criteria['min_downside_protection'])
        protection_score = min(20, (downside_protection * 1.0) + (excess_protection * aggressiveness))
        
        # Time preference score (max 15 points) - optimized for weekly options
        if preferred_dte_min <= days_to_expiry <= preferred_dte_max:
            time_score = 15
        elif days_to_expiry <= 3:  # Very short expiry gets bonus for weekly strategy
            time_score = 14
        elif days_to_expiry <= 7:  # Standard weekly range
            time_score = 12
        elif days_to_expiry <= 10: # Extended weekly range
            time_score = 9
        else:
            time_score = 4  # Penalize longer expiries for weekly strategy
        
        # Technical analysis bonus (max 15 points)
        technical_score = self._calculate_technical_score(symbol, grade)
        
        # Assignment risk penalty (adjusted for grade tolerance)
        assignment_tolerance = criteria['max_assignment_prob']
        if assignment_prob <= assignment_tolerance:
            assignment_penalty = 0  # No penalty if within tolerance
        else:
            excess_risk = assignment_prob - assignment_tolerance
            assignment_penalty = min(12, excess_risk * 0.25)
        
        # Grade bonus (better stocks get higher scores)
        grade_bonus = {
            'EXCELLENT': 10,
            'GOOD': 5,
            'FAIR': 0,
            'POOR': -5
        }.get(grade, 0)
        
        # Over-allocation penalty (max -8 points)
        allocation_penalty = max(0, (current_allocation_pct - 5) * 0.25)  # Penalty above 5%
        
        total_score = (return_score + protection_score + time_score + technical_score + grade_bonus 
                      - assignment_penalty - allocation_penalty)
        
        return max(0, min(100, total_score))
    
    def _calculate_technical_score(self, symbol: str, grade: str) -> float:
        """Calculate technical analysis score bonus.
        
        Args:
            symbol: Stock symbol
            grade: Stock grade
            
        Returns:
            Technical score (0-15 points)
        """
        technical_data = self._load_technical_data()
        symbol_data = technical_data.get(symbol, {})
        
        if not symbol_data:
            return 5  # Neutral score if no data
        
        try:
            indicators = symbol_data.get('technical_indicators', {})
            signals = symbol_data.get('signals', [])
            
            score = 5  # Base score
            
            # RSI scoring (max 3 points)
            rsi = indicators.get('rsi')
            if rsi is not None:
                if 30 <= rsi <= 70:  # Ideal range
                    score += 3
                elif 25 <= rsi <= 75:  # Good range
                    score += 2
                elif 20 <= rsi <= 80:  # Acceptable range
                    score += 1
                # Extreme levels get no bonus
            
            # Trend scoring (max 4 points)
            if 'STRONG UPTREND' in ' '.join(signals):
                score += 4
            elif 'EMA BULLISH ALIGNMENT' in ' '.join(signals):
                score += 3
            elif 'ABOVE LONG-TERM EMA' in ' '.join(signals):
                score += 2
            elif 'ABOVE 20-DAY MA' in ' '.join(signals):
                score += 1
            elif 'STRONG DOWNTREND' in ' '.join(signals):
                score -= 2  # Penalty for downtrend
            
            # Volume scoring (max 2 points)
            volume_ratio = indicators.get('volume_ratio', 0)
            if volume_ratio >= 0.8:
                score += 2
            elif volume_ratio >= 0.5:
                score += 1
            
            # Bollinger band position (max 2 points)
            current_price = symbol_data.get('current_price', 0)
            bb_upper = indicators.get('bollinger_upper', 0)
            bb_lower = indicators.get('bollinger_lower', 0)
            
            if bb_upper > bb_lower > 0:  # Valid Bollinger bands
                bb_position = (current_price - bb_lower) / (bb_upper - bb_lower)
                if 0.2 <= bb_position <= 0.8:  # Middle range - good for puts
                    score += 2
                elif 0.1 <= bb_position <= 0.9:  # Acceptable range
                    score += 1
            
            return min(15, max(0, score))
            
        except Exception as e:
            self.logger.warning(f"Error calculating technical score for {symbol}: {e}")
            return 5  # Neutral score on error
    
    def get_recommended_puts(self, account_snapshot: AccountSnapshot, min_score: float = 50.0) -> Dict[str, Any]:
        """Get recommended cash secured put opportunities using account data and wheel rankings.
        
        Args:
            account_snapshot: Current account snapshot
            min_score: Minimum attractiveness score to include
            
        Returns:
            Dictionary with recommended puts
        """
        self.logger.info("Getting recommended cash secured puts using data-driven approach")
        
        # Analyze opportunities using account data and wheel rankings
        opportunities = self.analyze_put_opportunities(
            account_snapshot.official_liquidation_value or Decimal('100000')
        )
        
        # Filter by minimum score and compile recommendations
        recommendations = {}
        total_analyzed = 0
        total_recommended = 0
        
        for symbol, data in opportunities.items():
            if 'error' in data:
                self.logger.debug(f"Skipping {symbol}: {data['error']}")
                continue
            
            total_analyzed += 1
            
            # Apply grade-specific minimum scores
            grade = data.get('grade', 'GOOD')
            grade_min_scores = {
                'EXCELLENT': max(min_score - 10, 30),  # More lenient for excellent stocks
                'GOOD': min_score,
                'FAIR': min_score + 5,  # Slightly more strict
                'POOR': min_score + 10  # Much more strict
            }
            effective_min_score = grade_min_scores.get(grade, min_score)
            
            good_puts = [
                put for put in data.get('put_opportunities', [])
                if put.get('attractiveness_score', 0) >= effective_min_score
            ]
            
            if good_puts:
                total_recommended += 1
                recommendations[symbol] = {
                    'symbol': symbol,
                    'grade': data['grade'],
                    'current_price': data['stock_data']['current_price'],
                    'current_allocation_pct': data['current_allocation_pct'],
                    'remaining_allocation_pct': data['remaining_allocation_pct'],
                    'criteria_applied': data['criteria'],
                    'recommended_puts': good_puts[:5],  # Top 5 recommendations
                    'total_opportunities': len(data.get('put_opportunities', [])),
                    'min_score_applied': effective_min_score,
                    'analysis_timestamp': data['analysis_timestamp']
                }
        
        self.logger.info(f"Analysis complete: {total_analyzed} symbols analyzed, {total_recommended} with recommendations")
        
        return recommendations


def find_cash_secured_put_opportunities(client, account_snapshot: AccountSnapshot,
                                       data_dir: str = "data", max_total_allocation_pct: float = 20.0) -> Dict[str, Any]:
    """Convenience function to find cash secured put opportunities using data-driven approach.
    
    Args:
        client: Broker client
        account_snapshot: Current account snapshot
        data_dir: Directory containing account and ranking data
        max_total_allocation_pct: Maximum total allocation per symbol
        
    Returns:
        Dictionary with put opportunities
    """
    engine = PutSelectionEngine(client, data_dir, max_total_allocation_pct)
    return engine.get_recommended_puts(account_snapshot)