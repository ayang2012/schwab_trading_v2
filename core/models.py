"""Data models for account snapshot and positions."""
from dataclasses import dataclass, asdict
from datetime import datetime
from decimal import Decimal
from typing import List, Optional


@dataclass
class StockPosition:
    symbol: str
    qty: int
    avg_cost: Decimal
    market_price: Decimal

    @property
    def market_value(self) -> Decimal:
        return Decimal(self.qty) * self.market_price

    @property
    def pnl(self) -> Decimal:
        return Decimal(self.qty) * (self.market_price - self.avg_cost)


@dataclass
class OptionPosition:
    symbol: str  # underlying
    contract_symbol: str
    qty: int
    avg_cost: Decimal
    market_price: Decimal
    strike: Decimal
    expiry: datetime
    put_call: str  # 'P' or 'C'

    @property
    def market_value(self) -> Decimal:
        return Decimal(self.qty) * self.market_price

    @property
    def pnl(self) -> Decimal:
        return Decimal(self.qty) * (self.market_price - self.avg_cost)
    
    @property
    def total_pnl(self) -> Decimal:
        """Total P&L for the entire option position (qty * 100 * per-share P&L)"""
        return Decimal(self.qty) * (self.market_price - self.avg_cost) * 100


@dataclass
class MutualFundPosition:
    symbol: str
    qty: int
    avg_cost: Decimal
    market_price: Decimal
    description: Optional[str] = None

    @property
    def market_value(self) -> Decimal:
        return Decimal(self.qty) * self.market_price

    @property
    def pnl(self) -> Decimal:
        return Decimal(self.qty) * (self.market_price - self.avg_cost)


@dataclass
class AccountSnapshot:
    generated_at: datetime
    cash: Decimal
    buying_power: Decimal
    stocks: List[StockPosition]
    options: List[OptionPosition]
    mutual_funds: List[MutualFundPosition]
    official_liquidation_value: Optional[Decimal] = None

    def to_dict(self):
        return asdict(self)
