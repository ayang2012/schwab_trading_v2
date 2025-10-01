"""Tests for data validation and real-time accuracy."""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from api.client import RealBrokerClient
from utils.config_schwab import SchwabConfig
from core.orchestrator import run_once
from core.models import AccountSnapshot


class TestDataValidation:
    """Test suite for validating real-time data accuracy and calculations."""
    
    @pytest.fixture
    def client(self):
        """Initialize real Schwab client for testing."""
        config = SchwabConfig.from_env()
        config.app_key = "ER0kVS2P0U9WMMlRRt7Mw4ELCmVRwTB5"
        config.app_secret = "3mJejG1MBpISgcjj"
        
        client = RealBrokerClient(
            app_key=config.app_key,
            app_secret=config.app_secret,
            redirect_uri=config.redirect_uri,
            token_path=config.token_path
        )
        return client
    
    def test_data_freshness(self, client):
        """Test that we're getting fresh, real-time data."""
        # Get two snapshots with a small delay
        result1 = run_once(client, include_technicals=False)
        
        import time
        time.sleep(2)  # Wait 2 seconds
        
        result2 = run_once(client, include_technicals=False)
        
        # Data should be fresh (timestamps should be different)
        snapshot1 = result1['snapshot']
        snapshot2 = result2['snapshot']
        
        assert snapshot1.generated_at != snapshot2.generated_at, "Timestamps should be different for fresh data"
        
        # Time difference should be reasonable (within last few minutes)
        time_diff = abs((snapshot2.generated_at - snapshot1.generated_at).total_seconds())
        assert time_diff >= 1, "Time difference should be at least 1 second"
        assert time_diff <= 300, "Time difference should be less than 5 minutes (data should be fresh)"
    
    def test_short_options_pnl_bounds(self, client):
        """Test that short options P&L never exceeds 100% (can't collect more than premium)."""
        result = run_once(client, include_technicals=True)
        snapshot = result['snapshot']
        technicals_data = result['data'].get('technicals', {})
        
        for option in snapshot.options:
            if option.qty < 0:  # Short position
                # Calculate P&L percentage manually
                premium_received = float(option.avg_cost)
                current_cost = float(option.market_price)
                
                if premium_received > 0:
                    max_profit_pct = (premium_received / premium_received) * 100  # Should be 100%
                    current_pnl_pct = ((premium_received - current_cost) / premium_received) * 100
                    
                    # P&L should never exceed 100% (can't collect more than the premium)
                    assert current_pnl_pct <= 100, f"Short option {option.contract_symbol} P&L {current_pnl_pct:.2f}% exceeds maximum possible 100%"
                    
                    # Also check the technical analysis P&L calculation
                    if option.contract_symbol in technicals_data.get('options', {}):
                        tech_data = technicals_data['options'][option.contract_symbol]
                        tech_pnl_pct = tech_data.get('position_data', {}).get('pnl_pct', 0)
                        
                        assert tech_pnl_pct <= 100, f"Technical analysis P&L {tech_pnl_pct:.2f}% exceeds maximum possible 100% for {option.contract_symbol}"
                        
                        print(f"✅ {option.contract_symbol}: P&L {tech_pnl_pct:.2f}% (within bounds)")
    
    def test_technical_indicators_reasonableness(self, client):
        """Test that technical indicators are within reasonable ranges."""
        result = run_once(client, include_technicals=True)
        technicals_data = result['data'].get('technicals', {})
        
        for symbol, data in technicals_data.get('stocks', {}).items():
            if 'technical_indicators' in data:
                indicators = data['technical_indicators']
                current_price = data['current_price']
                
                # RSI should be between 0 and 100
                rsi = indicators.get('rsi', 50)
                assert 0 <= rsi <= 100, f"{symbol} RSI {rsi} is out of range [0, 100]"
                
                # Moving averages should be positive
                for ma_type in ['sma_5', 'sma_10', 'sma_20', 'ema_10', 'ema_20', 'ema_50']:
                    ma_value = indicators.get(ma_type, 0)
                    assert ma_value > 0, f"{symbol} {ma_type} {ma_value} should be positive"
                    
                    # Moving averages should be reasonably close to current price (within 50%)
                    price_diff_pct = abs(ma_value - current_price) / current_price * 100
                    assert price_diff_pct <= 50, f"{symbol} {ma_type} {ma_value} is too far from current price {current_price} ({price_diff_pct:.1f}%)"
                
                # Bollinger bands should make sense
                bb_upper = indicators.get('bollinger_upper', 0)
                bb_lower = indicators.get('bollinger_lower', 0)
                
                assert bb_upper > bb_lower, f"{symbol} Bollinger upper {bb_upper} should be > lower {bb_lower}"
                assert bb_lower > 0, f"{symbol} Bollinger lower {bb_lower} should be positive"
                
                # Support should be <= current price <= resistance (usually)
                support = indicators.get('support_level', 0)
                resistance = indicators.get('resistance_level', float('inf'))
                
                assert support > 0, f"{symbol} support level {support} should be positive"
                assert resistance > support, f"{symbol} resistance {resistance} should be > support {support}"
                
                print(f"✅ {symbol}: All technical indicators within reasonable ranges")
    
    def test_account_value_consistency(self, client):
        """Test that account values are consistent and reasonable."""
        result = run_once(client, include_technicals=False)
        
        # Test basic consistency
        total_value = result['total_account_value']
        cash_balance = result['adjusted_cash_balance']
        buying_power = result['adjusted_buying_power']
        
        # Account value should be positive and reasonable
        assert total_value > 0, f"Total account value {total_value} should be positive"
        assert total_value < 10_000_000, f"Total account value {total_value} seems unreasonably high"
        
        # Cash balance should be positive
        assert cash_balance >= 0, f"Cash balance {cash_balance} should be non-negative"
        
        # Buying power can be negative (margin call) but shouldn't be extreme
        assert buying_power > -1_000_000, f"Buying power {buying_power} seems unreasonably negative"
        
        # Test position values
        snapshot = result['snapshot']
        
        # Stock positions should have reasonable values
        for stock in snapshot.stocks:
            assert stock.market_price > 0, f"Stock {stock.symbol} price {stock.market_price} should be positive"
            assert stock.market_price < 10_000, f"Stock {stock.symbol} price {stock.market_price} seems unreasonably high"
            
            # Market value should equal qty * price (approximately)
            expected_value = abs(stock.qty) * stock.market_price
            actual_value = abs(stock.market_value)
            value_diff_pct = abs(expected_value - actual_value) / expected_value * 100
            
            assert value_diff_pct < 1, f"Stock {stock.symbol} market value calculation off by {value_diff_pct:.2f}%"
        
        # Option positions should have reasonable values
        for option in snapshot.options:
            assert option.market_price >= 0, f"Option {option.contract_symbol} price {option.market_price} should be non-negative"
            assert option.market_price < 100, f"Option {option.contract_symbol} price {option.market_price} seems unreasonably high for an option"
            
            # Strike prices should be reasonable
            assert option.strike > 0, f"Option {option.contract_symbol} strike {option.strike} should be positive"
            assert option.strike < 10_000, f"Option {option.contract_symbol} strike {option.strike} seems unreasonably high"
            
            # Expiry should be in the future (or very recent past for expired options)
            days_to_expiry = (option.expiry - datetime.now()).days
            assert days_to_expiry >= -7, f"Option {option.contract_symbol} expired more than 7 days ago"
            assert days_to_expiry <= 365, f"Option {option.contract_symbol} expires more than 1 year from now"
        
        print(f"✅ Account values are consistent and reasonable")
    
    def test_cash_secured_put_collateral_calculation(self, client, caplog):
        """Test that cash secured put collateral is calculated correctly."""
        import logging
        
        # Set up logging to capture WARNING level messages
        caplog.set_level(logging.WARNING)
        
        result = run_once(client, include_technicals=False)
        snapshot = result['snapshot']
        
        # Calculate expected collateral manually
        expected_collateral = Decimal("0.00")
        for option in snapshot.options:
            if option.put_call.upper() == 'PUT' and option.qty < 0:  # Short puts
                collateral = abs(option.qty) * option.strike * 100
                expected_collateral += collateral
                
                print(f"Short put {option.contract_symbol}: {abs(option.qty)} contracts × ${option.strike} × 100 = ${collateral:,.2f}")
        
        # Find the collateral calculation in log messages
        collateral_found = False
        for record in caplog.records:
            if 'Cash Secured Put Collateral:' in record.message:
                # Extract the dollar amount
                import re
                match = re.search(r'\$([0-9,]+\.[0-9]{2})', record.message)
                if match:
                    calculated_collateral = Decimal(match.group(1).replace(',', ''))
                    
                    # Should match our manual calculation
                    assert abs(calculated_collateral - expected_collateral) < Decimal("0.01"), \
                        f"Collateral calculation mismatch: expected ${expected_collateral:,.2f}, got ${calculated_collateral:,.2f}"
                    
                    print(f"✅ Cash secured put collateral calculation correct: ${calculated_collateral:,.2f}")
                    collateral_found = True
                    break
        
        assert collateral_found, "Could not find cash secured put collateral in log messages"
    
    def test_multiple_runs_consistency(self, client):
        """Test that multiple runs within a short time period give consistent results."""
        results = []
        
        # Run multiple times quickly
        for i in range(3):
            result = run_once(client, include_technicals=False)
            results.append(result)
            
            if i < 2:  # Don't sleep after the last run
                import time
                time.sleep(1)
        
        # Account values should be very similar (market can move slightly)
        values = [r['total_account_value'] for r in results]
        
        # Check that values don't vary by more than 5% (market volatility)
        min_value = min(values)
        max_value = max(values)
        
        if min_value > 0:
            variation_pct = (max_value - min_value) / min_value * 100
            assert variation_pct <= 5, f"Account value varies too much: {variation_pct:.2f}% (${min_value:,.2f} to ${max_value:,.2f})"
        
        # Position counts should be identical
        position_counts = [(len(r['snapshot'].stocks), len(r['snapshot'].options)) for r in results]
        assert all(pc == position_counts[0] for pc in position_counts), "Position counts should be consistent"
        
        print(f"✅ Multiple runs are consistent: values range ${min_value:,.2f} to ${max_value:,.2f}")


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v"])