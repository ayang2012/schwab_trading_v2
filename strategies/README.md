# Option Trading Strategies

This package provides specialized modules for analyzing and selecting optimal option trading opportunities.

## Modules

### `put_selection.py` - Cash Secured Put Selection

Analyzes cash secured put opportunities for potential stock purchases:

- **Target Strategy**: Selling cash secured puts on stocks you'd like to own
- **Key Metrics**: 
  - Annualized return (premium/strike/days)
  - Downside protection ((current_price - strike)/current_price)
  - Assignment probability
  - Break-even price
- **Optimal Range**: 7-45 day expirations, OTM strikes
- **Scoring**: Prioritizes high returns with good downside protection

### `call_selection.py` - Covered Call Selection  

Analyzes covered call opportunities on existing stock positions:

- **Target Strategy**: Selling covered calls on stocks you own
- **Key Metrics**:
  - Annualized return (premium/stock_price/days) 
  - Assignment probability
  - Profit if assigned vs. opportunity cost
  - Premium as % of stock price
- **Optimal Range**: 7-45 day expirations, OTM strikes preferred
- **Scoring**: Balances income generation with assignment risk

## Usage

### Basic Usage

```python
from strategies.put_selection import find_cash_secured_put_opportunities
from strategies.call_selection import find_covered_call_opportunities
from api.client import RealBrokerClient

# Initialize client and get account data
client = RealBrokerClient()
snapshot = client.get_account_snapshot()

# Find covered call opportunities on existing positions
call_opps = find_covered_call_opportunities(client, snapshot)

# Find cash secured put opportunities on watchlist
watchlist = ['AAPL', 'MSFT', 'GOOGL']
put_opps = find_cash_secured_put_opportunities(client, watchlist, snapshot)
```

### Advanced Usage

```python
from strategies.put_selection import PutSelectionEngine
from strategies.call_selection import CallSelectionEngine

# Customize engines
put_engine = PutSelectionEngine(client, max_allocation_pct=5.0)
call_engine = CallSelectionEngine(client, min_premium_pct=1.5)

# Get detailed analysis
put_analysis = put_engine.analyze_put_opportunities(symbols, account_value)
call_analysis = call_engine.analyze_covered_call_opportunities(stock_positions)
```

## Key Features

### Intelligent Scoring System
Both engines use multi-factor scoring (0-100) that considers:
- **Returns**: Annualized premium income
- **Risk**: Assignment probability and downside protection
- **Time**: Optimal expiration windows (21-35 days preferred)
- **Portfolio**: Current allocation and diversification

### Risk Management
- **Position Sizing**: Respects maximum allocation limits
- **Assignment Analysis**: Estimates probability and outcomes
- **Diversification**: Considers current portfolio concentration
- **Liquidity**: Factors in open interest and volume

### Comprehensive Metrics
Each opportunity includes:
- Premium and pricing data (bid/ask/mark)
- Greeks (delta, theta, IV)
- Assignment probability and outcomes
- Profit scenarios and break-even analysis
- Risk-adjusted attractiveness scores

## Testing

Run the test script to see the strategies in action:

```bash
python3.11 scripts/test_option_strategies.py
```

This will analyze your current positions for covered calls and a sample watchlist for cash secured puts.

## Configuration

### Put Selection Parameters
- `max_allocation_pct`: Maximum allocation per position (default: 5.0%)
- `min_score`: Minimum attractiveness score (default: 60.0)
- Expiration range: 7-45 days
- Strike range: OTM puts (strike < current_price)

### Call Selection Parameters  
- `min_premium_pct`: Minimum premium % of stock price (default: 1.0%)
- `min_score`: Minimum attractiveness score (default: 50.0)  
- Expiration range: 7-45 days
- Strike range: OTM calls preferred (strike > current_price)

## Integration

These modules integrate seamlessly with:
- **Live Monitor**: Add option alerts to live_monitor.py
- **Wheel Strategy**: Coordinate put/call selection for wheel trading
- **Portfolio Analysis**: Use allocation data from account snapshots
- **Risk Management**: Respect position limits and diversification rules