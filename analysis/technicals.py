"""Technical analysis module for retrieving stock and options technicals.

This module provides functionality to:
1. Fetch technical indicators for stock holdings
2. Stream real-time options data for current positions
3. Calculate custom technical indicators
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
import logging

try:
    # Try relative imports first (when run as module from parent)
    from ..core.models import StockPosition, OptionPosition, AccountSnapshot
    from ..utils.logging import setup_logging
except ImportError:
    # Fall back to direct imports (when run from within directory)
    from core.models import StockPosition, OptionPosition, AccountSnapshot
    from utils.logging import setup_logging


class TechnicalAnalyzer:
    """Main class for technical analysis of stocks and options."""
    
    def __init__(self, client):
        """Initialize the TechnicalAnalyzer with a Schwab client.
        
        Args:
            client: Authenticated Schwab API client
        """
        self.client = client
        self.logger = logging.getLogger(__name__)
    
    def get_stock_technicals(self, snapshot: AccountSnapshot) -> Dict[str, Any]:
        """Get technical analysis for all stock positions.
        
        Args:
            snapshot: Account snapshot containing positions
            
        Returns:
            Dictionary with technical analysis for each stock position
        """
        self.logger.info("Fetching technical analysis for stock positions")
        
        technicals = {}
        stock_positions = snapshot.stocks
        
        self.logger.info(f"Analyzing {len(stock_positions)} stock positions")
        
        for position in stock_positions:
            try:
                self.logger.debug(f"Getting technicals for {position.symbol}")
                tech_data = self._calculate_stock_technicals(position)
                technicals[position.symbol] = tech_data
                
            except Exception as e:
                self.logger.error(f"Error getting technicals for {position.symbol}: {e}")
                technicals[position.symbol] = {"error": str(e)}
        
        return technicals
    
    def get_options_technicals_streaming(self, snapshot: AccountSnapshot) -> Dict[str, Any]:
        """Get real-time options technical analysis using streaming API.
        
        Args:
            snapshot: Account snapshot containing positions
            
        Returns:
            Dictionary with streaming technical analysis for each option position
        """
        self.logger.info("Setting up streaming options technical analysis")
        
        option_positions = snapshot.options
        
        if not option_positions:
            self.logger.info("No option positions found")
            return {}
        
        self.logger.info(f"Analyzing {len(option_positions)} option positions with streaming data")
        
        # Format contracts for streaming API
        formatted_contracts = []
        position_map = {}
        
        for position in option_positions:
            # Use the existing contract symbol directly (it's already in the correct format)
            formatted_contract = position.contract_symbol
            if not formatted_contract:
                self.logger.warning(f"Contract symbol is empty for position: {position.symbol} {position.strike} {position.put_call}")
                continue
            
            formatted_contracts.append(formatted_contract)
            position_map[formatted_contract] = position
        
        if not formatted_contracts:
            self.logger.error("No valid contracts formatted for streaming")
            return {}
        
        # Get streaming data
        streaming_data = self._get_streaming_options_data(formatted_contracts)
        
        # Process streaming data for each position
        technicals = {}
        for contract, stream_data in streaming_data.items():
            if contract in position_map:
                position = position_map[contract]
                try:
                    tech_data = self._parse_streaming_options_data(stream_data, position)
                    technicals[position.contract_symbol] = tech_data
                    
                except Exception as e:
                    self.logger.error(f"Error processing streaming data for {position.contract_symbol}: {e}")
                    # Fallback to options chain if streaming fails
                    fallback_data = self._get_options_chain_fallback(position)
                    technicals[position.contract_symbol] = fallback_data
        
        # For positions without streaming data, use fallback
        for position in option_positions:
            if position.contract_symbol not in technicals:
                self.logger.debug(f"Using fallback for {position.contract_symbol}")
                fallback_data = self._get_options_chain_fallback(position)
                technicals[position.contract_symbol] = fallback_data
        
        return technicals
    
    def _calculate_stock_technicals(self, position: StockPosition) -> Dict:
        """Calculate technical indicators for a stock position.
        
        Args:
            position: Stock position to analyze
            
        Returns:
            Dictionary with technical analysis data
        """
        try:
            # Get historical price data for calculations
            end_date = datetime.now()
            start_date = end_date - timedelta(days=60)  # 60 days for good MA calculation
            
            price_history = self.client.price_history(
                symbol=position.symbol,
                periodType='month',
                period=2,  # 2 months
                frequencyType='daily',
                frequency=1,
                startDate=start_date,
                endDate=end_date
            )
            
            if price_history.status_code != 200:
                return {"error": f"Failed to get price history: {price_history.status_code}"}
            
            candles = price_history.json().get('candles', [])
            
            if len(candles) < 20:
                return {"error": "Insufficient price history for technical analysis"}
            
            # Extract closing prices
            closes = [candle['close'] for candle in candles]
            highs = [candle['high'] for candle in candles]
            lows = [candle['low'] for candle in candles]
            volumes = [candle['volume'] for candle in candles]
            
            # Current price
            current_price = float(position.market_price)
            
            # Calculate technical indicators
            rsi = self._calculate_rsi(closes)
            sma_5 = sum(closes[-5:]) / 5
            sma_10 = sum(closes[-10:]) / 10
            sma_20 = sum(closes[-20:]) / 20
            
            # Calculate EMAs
            ema_10 = self._calculate_ema(closes, 10)
            ema_20 = self._calculate_ema(closes, 20)
            ema_50 = self._calculate_ema(closes, 50)
            
            # Bollinger Bands (20-period)
            bb_upper, bb_lower = self._calculate_bollinger_bands(closes[-20:])
            
            # Support and Resistance levels
            support_level = min(lows[-20:])
            resistance_level = max(highs[-20:])
            
            # Volume analysis
            avg_volume = sum(volumes[-20:]) / 20
            volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 1
            
            # Generate trading signals
            signals = self._generate_stock_signals(
                current_price, rsi, sma_5, sma_10, sma_20, ema_10, ema_20, ema_50,
                bb_upper, bb_lower, support_level, resistance_level, volume_ratio
            )
            
            return {
                "symbol": position.symbol,
                "current_price": current_price,
                "position_data": {
                    "quantity": position.qty,
                    "avg_cost": float(position.avg_cost),
                    "market_value": float(position.market_value),
                    "pnl": float(position.pnl),
                    "pnl_pct": round((current_price - float(position.avg_cost)) / float(position.avg_cost) * 100, 2) if position.avg_cost != 0 else 0
                },
                "technical_indicators": {
                    "rsi": round(rsi, 2),
                    "sma_5": round(sma_5, 2),
                    "sma_10": round(sma_10, 2),
                    "sma_20": round(sma_20, 2),
                    "ema_10": round(ema_10, 2),
                    "ema_20": round(ema_20, 2),
                    "ema_50": round(ema_50, 2),
                    "bollinger_upper": round(bb_upper, 2),
                    "bollinger_lower": round(bb_lower, 2),
                    "support_level": round(support_level, 2),
                    "resistance_level": round(resistance_level, 2),
                    "volume_ratio": round(volume_ratio, 2)
                },
                "signals": signals
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating technicals for {position.symbol}: {e}")
            return {"error": str(e)}
    
    def _format_contract_for_streaming(self, position: OptionPosition) -> Optional[str]:
        """Format option contract for Schwab streaming API.
        
        Format: [Underlying Symbol (6 chars) | Expiration (6 chars YYMMDD) | Call/Put (1 char) | Strike (8 chars)]
        Example: "AAPL  240517P00190000"
        
        Args:
            position: Option position to format
            
        Returns:
            Formatted contract symbol or None if formatting fails
        """
        try:
            # Underlying symbol - pad to 6 characters with spaces
            underlying = position.symbol.ljust(6)[:6]
            
            # Expiration date - format as YYMMDD
            expiry_str = position.expiry.strftime('%y%m%d')
            
            # Call/Put - single character (C or P, not CALL/PUT)
            option_type = 'C' if position.put_call.upper() == 'CALL' else 'P'
            
            # Strike price - format as 8 characters (5 before decimal, 3 after)
            strike_int = int(float(position.strike) * 1000)  # Convert to 3 decimal places
            strike_str = f"{strike_int:08d}"
            
            formatted = f"{underlying}{expiry_str}{option_type}{strike_str}"
            return formatted
            
        except Exception as e:
            self.logger.error(f"Error formatting contract {position.contract_symbol}: {e}")
            return None
    
    def _get_streaming_options_data(self, formatted_contracts: List[str]) -> Dict[str, Dict]:
        """Get real-time options data with Greeks using streaming API.
        
        Args:
            formatted_contracts: List of properly formatted contract symbols
            
        Returns:
            Dict mapping contract symbol to streaming data including Greeks
        """
        streaming_data = {}
        
        try:
            # Fields for Level One Options streaming including Greeks:
            # Based on schwabdev stream_fields.py mapping:
            # 0=Symbol, 1=Description, 2=Bid Price, 3=Ask Price, 4=Last Price, 5=High Price, 6=Low Price, 7=Close Price, 8=Total Volume
            # 9=Open Interest, 10=Volatility, 11=Money Intrinsic Value, 12=Expiration Year, 13=Multiplier, 14=Digits, 15=Open Price
            # 16=Bid Size, 17=Ask Size, 18=Last Size, 19=Net Change, 20=Strike Price, 21=Contract Type, 22=Underlying
            # 23=Expiration Month, 24=Deliverables, 25=Time Value, 26=Expiration Day, 27=Days to Expiration
            # 28=Delta, 29=Gamma, 30=Theta, 31=Vega, 32=Rho
            
            # Request comprehensive fields including all Greeks and market data
            fields = "0,1,2,3,4,5,6,7,8,9,10,16,17,18,19,20,25,27,28,29,30,31,32"
            
            # Use the streaming client
            streamer = self.client.stream
            
            self.logger.debug(f"Setting up Level One Options streaming for contracts: {formatted_contracts}")
            self.logger.debug(f"Requesting fields: {fields}")
            
            # Create streaming request for options with Greeks
            stream_request = streamer.level_one_options(formatted_contracts, fields)
            
            # For now, we'll use the options chain API as fallback to get real Greeks data
            # In production streaming implementation, you would:
            # 1. streamer.start()
            # 2. streamer.send(stream_request) 
            # 3. Collect streaming responses with Greeks data
            # 4. streamer.stop()
            
            self.logger.info(f"Options streaming request prepared for {len(formatted_contracts)} contracts")
            self.logger.info("Note: Full streaming implementation would collect real-time Greeks here")
            
            # For now, we'll try to get current Greeks from options chain data
            for contract in formatted_contracts:
                try:
                    # Parse the contract symbol to get underlying and strike info
                    # Format: AAL   251003C00011500
                    #         ^^^^^  ^^^^^^ ^^^^^^^^
                    #         under  expiry type+strike
                    if len(contract) >= 21:
                        underlying = contract[:6].strip()
                        expiry_str = contract[6:12]
                        option_type = contract[12]
                        strike_str = contract[13:21]
                        
                        # Convert strike from 8-digit format (e.g., "00011500" = $11.50)
                        self.logger.debug(f"Parsing contract {contract}: underlying='{underlying}', expiry='{expiry_str}', type='{option_type}', strike_str='{strike_str}'")
                        strike_price = float(strike_str) / 1000
                        
                        # Get current options chain data for this contract
                        greeks_data = self._get_options_greeks_from_chain(underlying, strike_price, expiry_str, option_type)
                        
                        streaming_data[contract] = {
                            "symbol": contract,
                            "underlying": underlying,
                            "strike": strike_price,
                            "option_type": option_type,
                            "streaming_fields_requested": fields,
                            "greeks": greeks_data,
                            "data_source": "options_chain_fallback",
                            "note": "In production, this would be real-time streaming data with Greeks"
                        }
                        
                except Exception as e:
                    self.logger.error(f"Error processing contract {contract}: {e}")
                    streaming_data[contract] = {
                        "symbol": contract,
                        "error": str(e),
                        "streaming_fields_requested": fields
                    }
            
        except Exception as e:
            self.logger.error(f"Error setting up options streaming: {e}")
            
        return streaming_data
    
    def _get_options_greeks_from_chain(self, underlying: str, strike: float, expiry_str: str, option_type: str) -> Dict:
        """Get options Greeks from options chain API as fallback.
        
        Args:
            underlying: Underlying symbol (e.g., 'AAPL')
            strike: Strike price (e.g., 95.0)
            expiry_str: Expiration in YYMMDD format
            option_type: 'C' for Call, 'P' for Put
            
        Returns:
            Dict containing Greeks data
        """
        try:
            # Convert expiry string to datetime for options chain query
            from datetime import datetime
            expiry_date = datetime.strptime(f"20{expiry_str}", "%Y%m%d")
            
            # Get options chain for this underlying and expiration  
            options_chain = self.client.option_chains(
                underlying, 
                fromDate=expiry_date.strftime("%Y-%m-%d"),
                toDate=expiry_date.strftime("%Y-%m-%d")
            )
            
            chain_data = None
            if options_chain.status_code == 200:
                chain_data = options_chain.json()
            
            if chain_data and 'callExpDateMap' in chain_data:
                # Look for our specific strike in the chain
                # The key format appears to be "YYYY-MM-DD:X" where X varies
                exp_date_str = expiry_date.strftime("%Y-%m-%d")
                
                option_map = chain_data.get('callExpDateMap' if option_type == 'C' else 'putExpDateMap', {})
                
                # Find the correct expiration key (it may have a suffix like :1, :4, etc.)
                exp_key = None
                for key in option_map.keys():
                    if key.startswith(exp_date_str):
                        exp_key = key
                        break
                
                if exp_key and exp_key in option_map:
                    strike_key = f"{strike:.1f}" 
                    if strike_key in option_map[exp_key]:
                        option_data = option_map[exp_key][strike_key][0]  # First contract at this strike
                        
                        return {
                            "delta": option_data.get('delta', 0),
                            "gamma": option_data.get('gamma', 0), 
                            "theta": option_data.get('theta', 0),
                            "vega": option_data.get('vega', 0),
                            "rho": option_data.get('rho', 0),
                            "implied_volatility": option_data.get('volatility', 0),
                            "time_value": option_data.get('timeValue', 0),
                            "theoretical_value": option_data.get('theoreticalValue', 0),
                            "bid": option_data.get('bid', 0),
                            "ask": option_data.get('ask', 0),
                            "last": option_data.get('last', 0),
                            "mark": option_data.get('mark', 0),
                            "open_interest": option_data.get('openInterest', 0),
                            "volume": option_data.get('totalVolume', 0),
                            "in_the_money": option_data.get('inTheMoney', False)
                        }
            
            # Return empty Greeks if not found
            return {
                "delta": 0, "gamma": 0, "theta": 0, "vega": 0, "rho": 0,
                "implied_volatility": 0, "time_value": 0, "theoretical_value": 0,
                "bid": 0, "ask": 0, "last": 0, "mark": 0, "open_interest": 0, "volume": 0,
                "in_the_money": False,
                "note": f"Greeks not found for {underlying} {strike} {option_type}"
            }
                        
        except Exception as e:
            self.logger.error(f"Error fetching Greeks for {underlying} {strike} {option_type}: {e}")
            return {
                "delta": 0, "gamma": 0, "theta": 0, "vega": 0, "rho": 0,
                "implied_volatility": 0, "time_value": 0, "theoretical_value": 0,
                "error": str(e)
            }
    
    def _parse_streaming_options_data(self, stream_data: Dict, position: OptionPosition) -> Dict:
        """Parse streaming options data including Greeks into technical analysis format.
        
        Args:
            stream_data: Raw streaming data from Schwab API including Greeks
            position: Option position
            
        Returns:
            Parsed technical data with Greeks
        """
        try:
            # Extract Greeks data from streaming response
            greeks = stream_data.get('greeks', {})
            
            # Calculate additional metrics
            days_to_expiry = (position.expiry - datetime.now()).days
            
            return {
                "contract_symbol": position.contract_symbol,
                "underlying_symbol": position.symbol, 
                "position_data": {
                    "quantity": position.qty,
                    "avg_cost": float(position.avg_cost),
                    "current_price": float(position.market_price),
                    "market_value": float(position.market_value),
                    "pnl": float(position.pnl),
                    "pnl_pct": self._calculate_options_pnl_pct(position)
                },
                "option_data": {
                    "strike": float(position.strike),
                    "expiry": position.expiry.strftime('%Y-%m-%d'),
                    "days_to_expiry": days_to_expiry,
                    "option_type": position.put_call
                },
                "greeks": {
                    "delta": round(greeks.get('delta', 0), 4),
                    "gamma": round(greeks.get('gamma', 0), 4),
                    "theta": round(greeks.get('theta', 0), 4),
                    "vega": round(greeks.get('vega', 0), 4),
                    "rho": round(greeks.get('rho', 0), 4),
                    "implied_volatility": round(greeks.get('implied_volatility', 0), 4)
                },
                "market_data": {
                    "bid": greeks.get('bid', 0),
                    "ask": greeks.get('ask', 0),
                    "last": greeks.get('last', 0),
                    "mark": greeks.get('mark', 0),
                    "volume": greeks.get('volume', 0),
                    "open_interest": greeks.get('open_interest', 0),
                    "time_value": round(greeks.get('time_value', 0), 4),
                    "theoretical_value": round(greeks.get('theoretical_value', 0), 4),
                    "in_the_money": greeks.get('in_the_money', False)
                },
                "signals": self._generate_options_signals_with_greeks(
                    position, 
                    greeks.get('delta', 0),
                    greeks.get('theta', 0), 
                    greeks.get('implied_volatility', 0),
                    days_to_expiry,
                    greeks.get('time_value', 0)
                ),
                "data_source": stream_data.get('data_source', 'streaming'),
                "streaming_info": {
                    "fields_requested": stream_data.get('streaming_fields_requested', ''),
                    "underlying_parsed": stream_data.get('underlying', ''),
                    "strike_parsed": stream_data.get('strike', 0)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing streaming data for {position.contract_symbol}: {e}")
            return {"error": str(e)}
    
    def _get_options_chain_fallback(self, position: OptionPosition) -> Dict:
        """Fallback method using options chain API when streaming is not available.
        
        Args:
            position: Option position
            
        Returns:
            Options data from chain API
        """
        try:
            # Get options chain for the underlying
            options_chain = self.client.option_chains(symbol=position.symbol)
            
            if options_chain.status_code == 200:
                chain_data = options_chain.json()
                return self._parse_options_data(chain_data, position)
            else:
                return {"error": f"Options chain API error: {options_chain.status_code}"}
                
        except Exception as e:
            self.logger.error(f"Fallback options chain failed for {position.contract_symbol}: {e}")
            return {"error": str(e)}
    
    def _parse_options_data(self, chain_data: Dict, position: OptionPosition) -> Dict:
        """Parse options chain data for technical analysis.
        
        Args:
            chain_data: Raw options chain data from API
            position: Option position to analyze
            
        Returns:
            Dictionary with options technical analysis
        """
        try:
            # Find the specific option contract in the chain
            option_data = None
            strike_str = str(float(position.strike))
            expiry_str = position.expiry.strftime('%Y-%m-%d')
            
            # Look through the options chain to find our contract
            if position.put_call.upper() == 'CALL':
                call_map = chain_data.get('callExpDateMap', {})
                for exp_date, strikes in call_map.items():
                    if expiry_str in exp_date:
                        for strike, option_list in strikes.items():
                            if strike_str in strike and option_list:
                                option_data = option_list[0]
                                break
            else:  # PUT
                put_map = chain_data.get('putExpDateMap', {})
                for exp_date, strikes in put_map.items():
                    if expiry_str in exp_date:
                        for strike, option_list in strikes.items():
                            if strike_str in strike and option_list:
                                option_data = option_list[0]
                                break
            
            if not option_data:
                return {
                    "contract_symbol": position.contract_symbol,
                    "error": "Contract not found in options chain"
                }
            
            # Extract key metrics
            bid = option_data.get('bid', 0)
            ask = option_data.get('ask', 0)
            last = option_data.get('last', float(position.market_price))
            volume = option_data.get('totalVolume', 0)
            open_interest = option_data.get('openInterest', 0)
            
            # Greeks
            delta = option_data.get('delta', 0)
            gamma = option_data.get('gamma', 0) 
            theta = option_data.get('theta', 0)
            vega = option_data.get('vega', 0)
            implied_volatility = option_data.get('volatility', 0)
            
            # Time to expiration
            days_to_expiry = (position.expiry - datetime.now()).days
            
            # Generate signals based on options metrics
            signals = self._generate_options_signals(
                position, implied_volatility, delta, theta, days_to_expiry, open_interest
            )
            
            return {
                "contract_symbol": position.contract_symbol,
                "underlying_symbol": position.symbol,
                "position_data": {
                    "quantity": position.qty,
                    "avg_cost": float(position.avg_cost),
                    "current_price": last,
                    "market_value": float(position.market_value),
                    "pnl": float(position.pnl),
                    "pnl_pct": round((last - float(position.avg_cost)) / float(position.avg_cost) * 100, 2) if position.avg_cost != 0 else 0
                },
                "option_metrics": {
                    "bid": bid,
                    "ask": ask,
                    "last": last,
                    "volume": volume,
                    "open_interest": open_interest,
                    "bid_ask_spread": round(ask - bid, 2) if ask > bid else 0,
                    "implied_volatility": round(implied_volatility * 100, 2)  # Convert to percentage
                },
                "greeks": {
                    "delta": round(delta, 4),
                    "gamma": round(gamma, 4),
                    "theta": round(theta, 4),
                    "vega": round(vega, 4)
                },
                "option_data": {
                    "strike": float(position.strike),
                    "expiry": expiry_str,
                    "days_to_expiry": days_to_expiry,
                    "option_type": position.put_call,
                    "moneyness": self._calculate_moneyness(chain_data.get('underlyingPrice', 0), float(position.strike), position.put_call)
                },
                "signals": signals
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing options data for {position.contract_symbol}: {e}")
            return {"error": str(e)}
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI (Relative Strength Index).
        
        Args:
            prices: List of closing prices
            period: RSI period (default 14)
            
        Returns:
            RSI value (0-100)
        """
        if len(prices) < period + 1:
            return 50  # Neutral RSI if insufficient data
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: float = 2) -> tuple:
        """Calculate Bollinger Bands.
        
        Args:
            prices: List of closing prices
            period: Moving average period
            std_dev: Number of standard deviations for bands
            
        Returns:
            Tuple of (upper_band, lower_band)
        """
        if len(prices) < period:
            sma = sum(prices) / len(prices)
            return sma, sma
        
        sma = sum(prices[-period:]) / period
        variance = sum((price - sma) ** 2 for price in prices[-period:]) / period
        std = variance ** 0.5
        
        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)
        
        return upper_band, lower_band
    
    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate Exponential Moving Average (EMA).
        
        Args:
            prices: List of closing prices
            period: EMA period
            
        Returns:
            EMA value
        """
        if len(prices) < period:
            return sum(prices) / len(prices) if prices else 0
        
        # Calculate smoothing factor (alpha)
        alpha = 2 / (period + 1)
        
        # Start with SMA for the first EMA value
        ema = sum(prices[:period]) / period
        
        # Calculate EMA for remaining values
        for price in prices[period:]:
            ema = (price * alpha) + (ema * (1 - alpha))
        
        return ema
    
    def _calculate_moneyness(self, underlying_price: float, strike_price: float, option_type: str) -> str:
        """Calculate option moneyness.
        
        Args:
            underlying_price: Current price of underlying
            strike_price: Strike price of option
            option_type: 'CALL' or 'PUT'
            
        Returns:
            Moneyness description
        """
        if option_type.upper() == 'CALL':
            if underlying_price > strike_price:
                return "In-The-Money"
            elif underlying_price == strike_price:
                return "At-The-Money"
            else:
                return "Out-Of-The-Money"
        else:  # PUT
            if underlying_price < strike_price:
                return "In-The-Money"
            elif underlying_price == strike_price:
                return "At-The-Money"
            else:
                return "Out-Of-The-Money"
    
    def _generate_stock_signals(self, current_price: float, rsi: float, sma_5: float, 
                               sma_10: float, sma_20: float, ema_10: float, ema_20: float, ema_50: float,
                               bb_upper: float, bb_lower: float, support: float, resistance: float, volume_ratio: float) -> List[str]:
        """Generate trading signals for stocks based on technical indicators.
        
        Args:
            current_price: Current stock price
            rsi: RSI value
            sma_5, sma_10, sma_20: Simple moving averages
            bb_upper, bb_lower: Bollinger band values
            support, resistance: Support and resistance levels
            volume_ratio: Current volume vs average volume
            
        Returns:
            List of signal strings
        """
        signals = []
        
        # RSI signals
        if rsi < 30:
            signals.append("OVERSOLD (RSI < 30)")
        elif rsi > 70:
            signals.append("OVERBOUGHT (RSI > 70)")
        
        # Moving average signals (SMA)
        if current_price > sma_5 > sma_10 > sma_20:
            signals.append("STRONG UPTREND (Price > MA5 > MA10 > MA20)")
        elif current_price < sma_5 < sma_10 < sma_20:
            signals.append("STRONG DOWNTREND (Price < MA5 < MA10 < MA20)")
        elif current_price > sma_20:
            signals.append("ABOVE 20-DAY MA")
        elif current_price < sma_20:
            signals.append("BELOW 20-DAY MA")
        
        # EMA-based signals (more responsive to recent price action)
        if ema_10 > ema_20 > ema_50:
            signals.append("EMA BULLISH ALIGNMENT (EMA10 > EMA20 > EMA50)")
        elif ema_10 < ema_20 < ema_50:
            signals.append("EMA BEARISH ALIGNMENT (EMA10 < EMA20 < EMA50)")
        
        # EMA crossover signals
        if current_price > ema_10 and current_price > ema_20:
            signals.append("ABOVE SHORT-TERM EMAs")
        elif current_price < ema_10 and current_price < ema_20:
            signals.append("BELOW SHORT-TERM EMAs")
        
        if current_price > ema_50:
            signals.append("ABOVE LONG-TERM EMA (50)")
        elif current_price < ema_50:
            signals.append("BELOW LONG-TERM EMA (50)")
        
        # Bollinger Band signals
        if current_price > bb_upper:
            signals.append("ABOVE UPPER BOLLINGER BAND")
        elif current_price < bb_lower:
            signals.append("BELOW LOWER BOLLINGER BAND")
        
        # Support/Resistance signals
        price_to_support = abs(current_price - support) / support * 100
        price_to_resistance = abs(current_price - resistance) / resistance * 100
        
        if price_to_support < 2:
            signals.append("NEAR SUPPORT LEVEL")
        if price_to_resistance < 2:
            signals.append("NEAR RESISTANCE LEVEL")
        
        # Volume signals
        if volume_ratio > 2:
            signals.append("HIGH VOLUME (2x+ avg)")
        elif volume_ratio > 1.5:
            signals.append("ELEVATED VOLUME")
        
        return signals if signals else ["NEUTRAL"]
    
    def _generate_options_signals(self, position: OptionPosition, iv: float, delta: Optional[float],
                                 theta: Optional[float], days_to_expiry: int, 
                                 open_interest: Optional[int]) -> List[str]:
        """Generate trading signals for options based on various metrics.
        
        Args:
            position: Option position
            iv: Implied volatility
            delta: Option delta
            theta: Option theta (time decay)
            days_to_expiry: Days until expiration
            open_interest: Open interest
            
        Returns:
            List of signal strings
        """
        signals = []
        
        # Time decay warnings
        if days_to_expiry <= 7:
            signals.append("EXPIRING SOON (≤7 days)")
        elif days_to_expiry <= 30:
            signals.append("SHORT TERM EXPIRY (≤30 days)")
        
        # Implied volatility signals (if available)
        if iv > 0:
            if iv > 0.5:  # 50%+ IV
                signals.append("HIGH IMPLIED VOLATILITY")
            elif iv < 0.2:  # 20%- IV
                signals.append("LOW IMPLIED VOLATILITY")
        
        # Delta signals (if available)
        if delta is not None:
            if position.put_call.upper() == 'CALL':
                if delta > 0.7:
                    signals.append("DEEP ITM CALL (Δ>0.7)")
                elif delta < 0.3:
                    signals.append("OTM CALL (Δ<0.3)")
            else:  # PUT
                if delta < -0.7:
                    signals.append("DEEP ITM PUT (Δ<-0.7)")
                elif delta > -0.3:
                    signals.append("OTM PUT (Δ>-0.3)")
        
        # Theta warnings (if available)
        if theta is not None and theta < -0.05:
            signals.append("HIGH TIME DECAY")
        
        # Liquidity concerns (if available)
        if open_interest is not None and open_interest < 100:
            signals.append("LOW LIQUIDITY")
        
        # P&L signals for options (considering short positions)
        if position.qty < 0:  # Short position (sold options)
            # For short options: profit when current price < premium received
            # P&L% = (premium_received - current_cost_to_close) / premium_received * 100
            premium_received = float(position.avg_cost)
            current_close_cost = float(position.market_price)
            pnl_pct = (premium_received - current_close_cost) / premium_received * 100
            
            if pnl_pct > 50:  # Made >50% of premium
                signals.append("STRONG PROFIT - CONSIDER CLOSING (+50%)")
            elif pnl_pct > 25:  # Made >25% of premium
                signals.append("GOOD PROFIT - CONSIDER CLOSING (+25%)")
            elif pnl_pct < -100:  # Current cost > 2x premium received
                signals.append("LARGE LOSS - CONSIDER CLOSING (-100%)")
        else:  # Long position (bought options)
            pnl_pct = (float(position.market_price) - float(position.avg_cost)) / float(position.avg_cost) * 100
            if pnl_pct > 20:
                signals.append("CONSIDER PROFIT TAKING (+20%)")
            elif pnl_pct < -50:
                signals.append("LARGE LOSS (-50%)")
        
        return signals if signals else ["MONITOR"]
    
    def _generate_options_signals_with_greeks(self, position: OptionPosition, delta: float, theta: float, 
                                            implied_volatility: float, days_to_expiry: int, 
                                            time_value: float) -> List[str]:
        """Generate enhanced trading signals for options using Greeks data.
        
        Args:
            position: Option position
            delta: Option delta
            theta: Option theta (time decay per day)
            implied_volatility: Implied volatility
            days_to_expiry: Days until expiration
            time_value: Time value of the option
            
        Returns:
            List of enhanced signal strings based on Greeks
        """
        signals = []
        
        # Time decay analysis using theta
        if days_to_expiry <= 7:
            if abs(theta) > 0.10:
                signals.append("EXTREME TIME DECAY - EXPIRING SOON (θ > 0.10)")
            else:
                signals.append("EXPIRING SOON (≤7 days)")
        elif days_to_expiry <= 21:
            if abs(theta) > 0.05:
                signals.append("HIGH TIME DECAY (θ > 0.05)")
            else:
                signals.append("MODERATE TIME DECAY")
        elif days_to_expiry <= 45:
            signals.append("THETA RISK INCREASING - APPROACHING 45 DTE")
        
        # Delta-based moneyness and directional risk
        if position.put_call.upper() == 'CALL':
            if delta > 0.8:
                signals.append("DEEP ITM CALL - HIGH DELTA RISK (Δ > 0.8)")
            elif delta > 0.6:
                signals.append("ITM CALL - STRONG DIRECTIONAL EXPOSURE (Δ > 0.6)")
            elif delta < 0.2:
                signals.append("LOW DELTA CALL - LIMITED UPSIDE SENSITIVITY (Δ < 0.2)")
            elif 0.4 <= delta <= 0.6:
                signals.append("ATM CALL - MAXIMUM GAMMA RISK")
        else:  # PUT
            if delta < -0.8:
                signals.append("DEEP ITM PUT - HIGH DELTA RISK (Δ < -0.8)")
            elif delta < -0.6:
                signals.append("ITM PUT - STRONG DIRECTIONAL EXPOSURE (Δ < -0.6)")
            elif delta > -0.2:
                signals.append("LOW DELTA PUT - LIMITED DOWNSIDE SENSITIVITY (Δ > -0.2)")
            elif -0.6 <= delta <= -0.4:
                signals.append("ATM PUT - MAXIMUM GAMMA RISK")
        
        # Implied volatility analysis
        if implied_volatility > 0.6:  # 60%+ IV
            signals.append("VERY HIGH IV - VOLATILITY CRUSH RISK (IV > 60%)")
        elif implied_volatility > 0.4:  # 40%+ IV
            signals.append("HIGH IV - ELEVATED PREMIUM (IV > 40%)")
        elif implied_volatility < 0.15:  # 15%- IV
            signals.append("LOW IV - CHEAP PREMIUM (IV < 15%)")
        elif implied_volatility < 0.25:  # 25%- IV
            signals.append("MODERATE IV - REASONABLE PREMIUM")
        
        # Time value and intrinsic value analysis
        current_price = float(position.market_price)
        if time_value > 0:
            time_value_pct = (time_value / current_price) * 100
            if time_value_pct > 50:
                signals.append("HIGH TIME VALUE (>50% of premium)")
            elif time_value_pct < 10 and days_to_expiry > 30:
                signals.append("LOW TIME VALUE - MOSTLY INTRINSIC")
        
        # Position-specific P&L analysis with Greeks context
        if position.qty < 0:  # Short position
            premium_received = float(position.avg_cost)
            current_close_cost = float(position.market_price)
            pnl_pct = (premium_received - current_close_cost) / premium_received * 100
            
            if pnl_pct > 75:
                signals.append("EXCELLENT SHORT PROFIT - CONSIDER CLOSING (>75%)")
            elif pnl_pct > 50:
                signals.append("STRONG SHORT PROFIT - THETA WORKING (>50%)")
            elif pnl_pct > 25:
                signals.append("GOOD SHORT PROFIT - MONITOR DELTA RISK (>25%)")
            elif pnl_pct < -50:
                signals.append("LARGE SHORT LOSS - HIGH DELTA AGAINST US (<-50%)")
            
            # Short-specific Greeks warnings
            if abs(delta) > 0.6:
                signals.append("HIGH DELTA RISK - SHORT POSITION VULNERABLE")
            if abs(theta) < 0.02 and days_to_expiry > 30:
                signals.append("LOW THETA BENEFIT - TIME DECAY SLOW")
                
        else:  # Long position  
            pnl_pct = (current_price - float(position.avg_cost)) / float(position.avg_cost) * 100
            
            if pnl_pct > 100:
                signals.append("EXCEPTIONAL LONG PROFIT - SECURE GAINS (>100%)")
            elif pnl_pct > 50:
                signals.append("STRONG LONG PROFIT - CONSIDER PARTIAL CLOSE (>50%)")
            elif pnl_pct > 25:
                signals.append("GOOD LONG PROFIT - MONITOR THETA DECAY (>25%)")
            elif pnl_pct < -75:
                signals.append("SEVERE LONG LOSS - CUT LOSSES? (<-75%)")
            elif pnl_pct < -50:
                signals.append("LARGE LONG LOSS - THETA & DELTA WORKING AGAINST (<-50%)")
            
            # Long-specific Greeks warnings
            if abs(theta) > 0.05 and days_to_expiry < 30:
                signals.append("HIGH THETA DECAY - TIME WORKING AGAINST LONG")
            if abs(delta) < 0.2:
                signals.append("LOW DELTA - NEEDS LARGE UNDERLYING MOVE")
        
        # Volatility environment signals for both long and short
        if implied_volatility > 0.5 and position.qty < 0:
            signals.append("IV CRUSH OPPORTUNITY - SHORT PREMIUM")
        elif implied_volatility < 0.2 and position.qty > 0:
            signals.append("CHEAP PREMIUM ENTRY - LONG OPPORTUNITY")
        
        # Risk management based on time and Greeks
        if days_to_expiry <= 21 and abs(theta) > 0.05:
            signals.append("THETA ACCELERATION ZONE - MANAGE ACTIVELY")
        
        if days_to_expiry <= 7 and abs(delta) > 0.3:
            signals.append("PIN RISK - NEAR EXPIRY WITH DELTA EXPOSURE")
        
        return signals if signals else ["MONITOR - GREEKS NEUTRAL"]
    
    def _calculate_options_pnl_pct(self, position):
        """Calculate P&L percentage for options positions based on position type"""
        try:
            avg_cost = float(position.avg_cost)
            current_price = float(position.market_price)
            quantity = int(position.qty)
            
            self.logger.debug(f"P&L Debug - {position.contract_symbol}: qty={quantity}, avg_cost={avg_cost}, current_price={current_price}")
            
            if avg_cost == 0:
                return 0
            
            # For short positions (negative quantity), we sold options and collected premium
            if quantity < 0:
                # P&L = (premium_received - current_cost) / premium_received * 100
                premium_received = abs(avg_cost)  # Cost basis is the premium we received
                current_cost = current_price      # Current cost to buy back
                pnl_pct = ((premium_received - current_cost) / premium_received) * 100
                self.logger.debug(f"Short position calc: premium_received={premium_received}, current_cost={current_cost}, pnl_pct={pnl_pct}")
                return round(pnl_pct, 2)
            else:
                # For long positions, use traditional P&L calculation
                pnl_pct = ((current_price - avg_cost) / avg_cost) * 100
                self.logger.debug(f"Long position calc: pnl_pct={pnl_pct}")
                return round(pnl_pct, 2)
                
        except (ValueError, ZeroDivisionError):
            return 0


def analyze_account_technicals(client, snapshot: AccountSnapshot) -> Dict[str, Any]:
    """Main entry point for account technical analysis.
    
    Args:
        client: Schwab API client
        snapshot: Account snapshot containing positions
        
    Returns:
        Dictionary with complete technical analysis
    """
    analyzer = TechnicalAnalyzer(client)
    
    # Get stock technicals
    stock_technicals = analyzer.get_stock_technicals(snapshot)
    
    # Get options technicals with streaming
    options_technicals = analyzer.get_options_technicals_streaming(snapshot)
    
    return {
        "stocks": stock_technicals,
        "options": options_technicals,
        "summary": {
            "total_stocks_analyzed": len(stock_technicals),
            "total_options_analyzed": len(options_technicals),
            "stock_signals": _summarize_stock_signals(stock_technicals),
            "options_signals": _summarize_options_signals(options_technicals)
        }
    }


def _summarize_stock_signals(stock_technicals: Dict[str, Any]) -> Dict[str, int]:
    """Summarize stock signals across all positions.
    
    Args:
        stock_technicals: Stock technical analysis data
        
    Returns:
        Summary of signal counts
    """
    signal_counts = {}
    
    for symbol, data in stock_technicals.items():
        if "signals" in data and isinstance(data["signals"], list):
            for signal in data["signals"]:
                signal_counts[signal] = signal_counts.get(signal, 0) + 1
    
    return signal_counts


def _summarize_options_signals(options_technicals: Dict[str, Any]) -> Dict[str, int]:
    """Summarize options signals across all positions.
    
    Args:
        options_technicals: Options technical analysis data
        
    Returns:
        Summary of signal counts
    """
    signal_counts = {}
    
    for contract, data in options_technicals.items():
        if "signals" in data and isinstance(data["signals"], list):
            for signal in data["signals"]:
                signal_counts[signal] = signal_counts.get(signal, 0) + 1
    
    return signal_counts


def get_technicals_for_symbol(symbol: str, client=None) -> Dict[str, Any]:
    """
    Get technical analysis for any stock or option symbol.
    
    Args:
        symbol: Stock ticker (e.g., 'AAPL') or option symbol (e.g., 'AAPL  241220C00150000')
        client: Optional broker client. If None, uses SimBrokerClient for demo data.
        
    Returns:
        Dictionary containing technical indicators and analysis
        
    Example:
        # Stock analysis
        technicals = get_technicals_for_symbol('AAPL')
        print(f"RSI: {technicals.get('rsi', 'N/A')}")
        
        # Option analysis  
        technicals = get_technicals_for_symbol('AAPL  241220C00150000')
        print(f"Delta: {technicals.get('delta', 'N/A')}")
    """
    if client is None:
        from api.sim_client import SimBrokerClient
        client = SimBrokerClient()
    
    # Initialize analyzer
    analyzer = TechnicalAnalyzer(client)
    
    # Determine if it's a stock or option symbol
    if len(symbol) > 10 and ' ' in symbol:
        # Looks like an option symbol
        return _get_option_technicals_for_symbol(symbol, analyzer, client)
    else:
        # Treat as stock symbol
        return _get_stock_technicals_for_symbol(symbol, analyzer, client)


def _get_stock_technicals_for_symbol(symbol: str, analyzer: TechnicalAnalyzer, client) -> Dict[str, Any]:
    """Get technical analysis for a stock symbol."""
    # For now, return mock technical data
    # In a production system, this would fetch real market data and calculate actual technicals
    
    import random
    import math
    
    # Generate some realistic-looking mock data
    base_price = random.uniform(50, 300)  # Random base price
    rsi = random.uniform(20, 80)  # RSI between 20-80
    
    # Create mock technical indicators
    technicals = {
        'symbol': symbol,
        'type': 'stock',
        'timestamp': datetime.now().isoformat(),
        'calculation_method': 'mock_data',
        
        # Technical indicators
        'rsi': round(rsi, 2),
        'sma_20': round(base_price * random.uniform(0.95, 1.05), 2),
        'sma_50': round(base_price * random.uniform(0.90, 1.10), 2),
        'macd': round(random.uniform(-2.0, 2.0), 3),
        'macd_signal': round(random.uniform(-1.5, 1.5), 3),
        'macd_histogram': round(random.uniform(-1.0, 1.0), 3),
        
        # Bollinger Bands
        'bollinger_bands': {
            'upper': round(base_price * 1.1, 2),
            'middle': round(base_price, 2),
            'lower': round(base_price * 0.9, 2)
        },
        
        # Volume and momentum
        'volume_avg_10': random.randint(1000000, 50000000),
        'price_change_pct': round(random.uniform(-5.0, 5.0), 2),
        
        # Generate signals based on indicators
        'signals': _generate_mock_signals(rsi, base_price),
        
        # Market info
        'market_price': round(base_price, 2),
        'price_range': {
            'day_high': round(base_price * random.uniform(1.01, 1.05), 2),
            'day_low': round(base_price * random.uniform(0.95, 0.99), 2),
            '52_week_high': round(base_price * random.uniform(1.2, 2.0), 2),
            '52_week_low': round(base_price * random.uniform(0.5, 0.8), 2)
        }
    }
    
    return technicals


def _generate_mock_signals(rsi: float, price: float) -> List[str]:
    """Generate mock trading signals based on mock indicators."""
    signals = []
    
    if rsi < 30:
        signals.append('OVERSOLD')
    elif rsi > 70:
        signals.append('OVERBOUGHT')
    else:
        signals.append('NEUTRAL_RSI')
    
    # Random additional signals
    signal_options = ['BULLISH_MOMENTUM', 'BEARISH_MOMENTUM', 'SIDEWAYS_TREND', 
                     'VOLUME_SPIKE', 'BREAKOUT_POTENTIAL', 'SUPPORT_LEVEL', 'RESISTANCE_LEVEL']
    
    # Add 1-2 random signals
    import random
    num_signals = random.randint(1, 2)
    additional_signals = random.sample(signal_options, num_signals)
    signals.extend(additional_signals)
    
    return signals


def _get_option_technicals_for_symbol(symbol: str, analyzer: TechnicalAnalyzer, client) -> Dict[str, Any]:
    """Get technical analysis for an option symbol."""
    try:
        # Parse option symbol
        from utils.assignments import extract_option_details
        option_details = extract_option_details(symbol)
        
        if not option_details:
            return {
                'symbol': symbol,
                'type': 'option',
                'error': 'Invalid option symbol format',
                'timestamp': datetime.now().isoformat()
            }
        
        # Generate mock option data
        import random
        from datetime import date
        
        # Calculate days to expiration
        days_to_expiry = (option_details['expiry'] - date.today()).days
        
        # Mock underlying price (would normally fetch real data)
        underlying_price = random.uniform(100, 300)
        strike = option_details['strike']
        is_call = option_details['option_type'] == 'CALL'
        
        # Calculate mock intrinsic value
        if is_call:
            intrinsic_value = max(0, underlying_price - strike)
        else:  # PUT
            intrinsic_value = max(0, strike - underlying_price)
        
        # Mock time value and premium
        time_value = random.uniform(0.1, 5.0) * (days_to_expiry / 30.0)  # Decays with time
        premium = intrinsic_value + time_value
        
        # Mock Greeks (would normally come from Black-Scholes or market data)
        delta = random.uniform(0.1, 0.9) if is_call else random.uniform(-0.9, -0.1)
        gamma = random.uniform(0.01, 0.1)
        theta = random.uniform(-0.1, -0.01)  # Always negative (time decay)
        vega = random.uniform(0.05, 0.3)
        rho = random.uniform(0.01, 0.05) if is_call else random.uniform(-0.05, -0.01)
        
        technicals = {
            'symbol': symbol,
            'type': 'option',
            'timestamp': datetime.now().isoformat(),
            'calculation_method': 'mock_data',
            
            # Option details
            'underlying': option_details['ticker'],
            'underlying_price': round(underlying_price, 2),
            'strike': strike,
            'option_type': option_details['option_type'],
            'expiry': option_details['expiry'].strftime('%Y-%m-%d'),
            'days_to_expiration': days_to_expiry,
            
            # Pricing
            'premium': round(premium, 2),
            'bid': round(premium * 0.98, 2),
            'ask': round(premium * 1.02, 2),
            'intrinsic_value': round(intrinsic_value, 2),
            'time_value': round(time_value, 2),
            
            # Greeks
            'delta': round(delta, 4),
            'gamma': round(gamma, 4),
            'theta': round(theta, 4),
            'vega': round(vega, 4),
            'rho': round(rho, 4),
            
            # Risk metrics
            'implied_volatility': round(random.uniform(0.15, 0.60), 4),  # 15-60% IV
            'open_interest': random.randint(100, 10000),
            'volume': random.randint(10, 1000),
            
            # Analysis
            'moneyness': 'ITM' if intrinsic_value > 0 else 'OTM',
            'liquidity': 'HIGH' if random.random() > 0.5 else 'MEDIUM',
            'signals': _generate_mock_option_signals(delta, theta, days_to_expiry, intrinsic_value > 0)
        }
        
        return technicals
        
    except Exception as e:
        logging.getLogger(__name__).error(f"Error getting option technicals for {symbol}: {e}")
        return {
            'symbol': symbol,
            'type': 'option', 
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


def _generate_mock_option_signals(delta: float, theta: float, days_to_expiry: int, is_itm: bool) -> List[str]:
    """Generate mock trading signals for options based on mock Greeks and conditions."""
    signals = []
    
    # Delta-based signals
    if abs(delta) > 0.7:
        signals.append('HIGH_DELTA')
    elif abs(delta) < 0.3:
        signals.append('LOW_DELTA')
    
    # Time decay signals
    if days_to_expiry < 7:
        signals.append('HIGH_TIME_DECAY')
    elif days_to_expiry < 30:
        signals.append('MODERATE_TIME_DECAY')
    
    # Moneyness signals
    if is_itm:
        signals.append('IN_THE_MONEY')
    else:
        signals.append('OUT_OF_THE_MONEY')
    
    # Random additional signals
    import random
    additional_signals = ['HIGH_IMPLIED_VOL', 'LOW_IMPLIED_VOL', 'EARNINGS_PLAY', 
                         'TECHNICAL_BREAKOUT', 'VOLUME_SPIKE', 'UNUSUAL_ACTIVITY']
    
    if random.random() > 0.6:  # 40% chance of additional signal
        signals.append(random.choice(additional_signals))
    
    return signals