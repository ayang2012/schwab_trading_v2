"""Tests for models.py - data classes and business logic."""
import pytest
from datetime import datetime
from decimal import Decimal
from core.models import StockPosition, OptionPosition, MutualFundPosition, AccountSnapshot


class TestStockPosition:
    """Test StockPosition calculations and properties."""
    
    def test_market_value_calculation(self):
        """Test that market value is correctly calculated."""
        position = StockPosition(
            symbol="AAPL",
            qty=100,
            avg_cost=Decimal("150.00"),
            market_price=Decimal("175.25")
        )
        expected_value = Decimal("17525.00")  # 100 * 175.25
        assert position.market_value == expected_value
    
    def test_pnl_calculation_positive(self):
        """Test P&L calculation for profitable position."""
        position = StockPosition(
            symbol="AAPL",
            qty=100,
            avg_cost=Decimal("150.00"),
            market_price=Decimal("175.25")
        )
        expected_pnl = Decimal("2525.00")  # 100 * (175.25 - 150.00)
        assert position.pnl == expected_pnl
    
    def test_pnl_calculation_negative(self):
        """Test P&L calculation for losing position."""
        position = StockPosition(
            symbol="INTC",
            qty=200,
            avg_cost=Decimal("52.00"),
            market_price=Decimal("46.50")
        )
        expected_pnl = Decimal("-1100.00")  # 200 * (46.50 - 52.00)
        assert position.pnl == expected_pnl


class TestOptionPosition:
    """Test OptionPosition calculations and properties."""
    
    def test_market_value_calculation(self):
        """Test that option market value is correctly calculated."""
        position = OptionPosition(
            symbol="AAPL",
            contract_symbol="AAPL250117C00180000",
            qty=2,
            avg_cost=Decimal("5.50"),
            market_price=Decimal("12.75"),
            strike=Decimal("180.00"),
            expiry=datetime(2025, 1, 17),
            put_call="C"
        )
        expected_value = Decimal("25.50")  # 2 * 12.75
        assert position.market_value == expected_value
    
    def test_short_option_market_value(self):
        """Test market value for short option positions."""
        position = OptionPosition(
            symbol="INTC",
            contract_symbol="INTC241115P00045000",
            qty=-3,
            avg_cost=Decimal("2.25"),
            market_price=Decimal("4.10"),
            strike=Decimal("45.00"),
            expiry=datetime(2024, 11, 15),
            put_call="P"
        )
        expected_value = Decimal("-12.30")  # -3 * 4.10
        assert position.market_value == expected_value


class TestMutualFundPosition:
    """Test MutualFundPosition calculations and properties."""
    
    def test_mutual_fund_market_value(self):
        """Test mutual fund market value calculation."""
        position = MutualFundPosition(
            symbol="SWVXX",
            qty=100000,
            avg_cost=Decimal("1.00"),
            market_price=Decimal("1.00"),
            description="Schwab Prime Advantage Money Fund"
        )
        expected_value = Decimal("100000.00")  # 100000 * 1.00
        assert position.market_value == expected_value
    
    def test_mutual_fund_pnl(self):
        """Test mutual fund P&L calculation (usually zero for money market funds)."""
        position = MutualFundPosition(
            symbol="SWVXX",
            qty=100000,
            avg_cost=Decimal("1.00"),
            market_price=Decimal("1.00")
        )
        expected_pnl = Decimal("0.00")  # 100000 * (1.00 - 1.00)
        assert position.pnl == expected_pnl


class TestAccountSnapshot:
    """Test AccountSnapshot data structure."""
    
    def test_account_snapshot_creation(self):
        """Test creating an AccountSnapshot with all position types."""
        stocks = [
            StockPosition(
                symbol="AAPL",
                qty=100,
                avg_cost=Decimal("150.00"),
                market_price=Decimal("175.25")
            )
        ]
        
        options = [
            OptionPosition(
                symbol="AAPL",
                contract_symbol="AAPL250117C00180000",
                qty=2,
                avg_cost=Decimal("5.50"),
                market_price=Decimal("12.75"),
                strike=Decimal("180.00"),
                expiry=datetime(2025, 1, 17),
                put_call="C"
            )
        ]
        
        mutual_funds = [
            MutualFundPosition(
                symbol="SWVXX",
                qty=100000,
                avg_cost=Decimal("1.00"),
                market_price=Decimal("1.00")
            )
        ]
        
        snapshot = AccountSnapshot(
            generated_at=datetime.utcnow(),
            cash=Decimal("1000.00"),
            buying_power=Decimal("5000.00"),
            stocks=stocks,
            options=options,
            mutual_funds=mutual_funds,
            official_liquidation_value=Decimal("118550.50")
        )
        
        assert len(snapshot.stocks) == 1
        assert len(snapshot.options) == 1
        assert len(snapshot.mutual_funds) == 1
        assert snapshot.cash == Decimal("1000.00")
        assert snapshot.official_liquidation_value == Decimal("118550.50")
    
    def test_to_dict_method(self):
        """Test that AccountSnapshot can be converted to dictionary."""
        snapshot = AccountSnapshot(
            generated_at=datetime(2025, 1, 1, 12, 0, 0),
            cash=Decimal("1000.00"),
            buying_power=Decimal("5000.00"),
            stocks=[],
            options=[],
            mutual_funds=[],
            official_liquidation_value=None
        )
        
        snapshot_dict = snapshot.to_dict()
        assert isinstance(snapshot_dict, dict)
        assert snapshot_dict['cash'] == Decimal("1000.00")
        assert snapshot_dict['buying_power'] == Decimal("5000.00")
        assert snapshot_dict['stocks'] == []