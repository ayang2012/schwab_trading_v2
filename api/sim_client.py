"""Simulated broker client for development and testing."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

try:
    # Try relative imports first (when run as module from parent)
    from ..core.models import AccountSnapshot, StockPosition, OptionPosition, MutualFundPosition
except ImportError:
    # Fall back to direct imports (when run from within directory)
    from core.models import AccountSnapshot, StockPosition, OptionPosition, MutualFundPosition


@dataclass
class SimBrokerClient:
    """A deterministic simulator used for development and tests."""

    def get_account_snapshot(self) -> AccountSnapshot:
        """Return simulated account data for testing purposes."""
        now = datetime.utcnow()
        stocks = [
            StockPosition(symbol="AAPL", qty=100, avg_cost=Decimal("150.00"), market_price=Decimal("180.50")),
            StockPosition(symbol="INTC", qty=200, avg_cost=Decimal("30.00"), market_price=Decimal("35.10")),
        ]
        options = [
            OptionPosition(
                symbol="AAPL",
                contract_symbol="250930C00180000",
                qty=-2,
                avg_cost=Decimal("2.50"),
                market_price=Decimal("1.75"),
                strike=Decimal("180.00"),
                expiry=now + timedelta(days=10),
                put_call="C",
            ),
            OptionPosition(
                symbol="INTC",
                contract_symbol="250930P00035000",
                qty=-1,
                avg_cost=Decimal("3.00"),
                market_price=Decimal("2.25"),
                strike=Decimal("35.00"),
                expiry=now + timedelta(days=10),
                put_call="P",
            ),
        ]
        return AccountSnapshot(
            generated_at=now,
            cash=Decimal("100000.00"),
            buying_power=Decimal("250000.00"),
            stocks=stocks,
            options=options,
            mutual_funds=[],
            official_liquidation_value=None,
        )