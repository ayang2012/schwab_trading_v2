"""Simple orchestrator for v2 to capture a consistent account snapshot."""
from pathlib import Path
from datetime import datetime
from decimal import Decimal

try:
    # Try relative imports first (when run as module from parent)
    from ..utils.io import safe_write_json
    from ..utils.logging import get_logger
    from ..analysis.technicals import analyze_account_technicals
    from ..utils.assignments import fetch_and_record_assignments
    from ..utils.db_utils import AssignmentDB
except ImportError:
    # Fall back to direct imports (when run from within directory)
    from utils.io import safe_write_json
    from utils.logging import get_logger
    from analysis.technicals import analyze_account_technicals
    from utils.assignments import fetch_and_record_assignments
    from utils.db_utils import AssignmentDB


def run_once(client, out_dir: Path | None = None, include_technicals: bool = False, check_assignments: bool = True):
    logger = get_logger()
    out_dir = out_dir or Path("./data/account")
    out_dir = Path(out_dir)
    snapshot = client.get_account_snapshot()
    
    # Check for new option assignments
    if check_assignments:
        try:
            db = AssignmentDB()
            new_assignments = fetch_and_record_assignments(client, db, lookback_days=3)
            if new_assignments:
                logger.warning(f"🚨 {len(new_assignments)} NEW OPTION ASSIGNMENTS DETECTED:")
                for assignment in new_assignments:
                    logger.warning(f"   ⚠️  {assignment['ticker']}: {assignment['shares']} shares at ${assignment['price_per_share']:.2f}")
                    logger.warning(f"      Contract: {assignment['option_symbol']}")
        except Exception as e:
            logger.error(f"Assignment check failed: {e}")
            # Don't fail the main process for assignment check errors
    
    # Calculate total account value
    total_stock_value = sum(s.market_value for s in snapshot.stocks)
    total_option_value = sum(o.market_value for o in snapshot.options)
    total_mutual_fund_value = sum(m.market_value for m in snapshot.mutual_funds)
    calculated_value = snapshot.cash + total_stock_value + total_option_value + total_mutual_fund_value
    
    # Use official liquidation value if available (more accurate for margin accounts)
    total_account_value = snapshot.official_liquidation_value if snapshot.official_liquidation_value is not None else calculated_value
    
    # Calculate adjusted cash balance and buying power per user's requirements
    # Cash balance = mutual fund value
    adjusted_cash_balance = total_mutual_fund_value
    
    # Calculate cash secured put options collateral (short puts)
    cash_secured_put_collateral = Decimal("0.00")
    for option in snapshot.options:
        if option.put_call.upper() == 'PUT' and option.qty < 0:  # Short puts
            # Collateral = abs(qty) * strike * 100 (contract multiplier)
            collateral = abs(option.qty) * option.strike * 100
            cash_secured_put_collateral += collateral
    
    # Buying power = API buying power + cash balance - cash secured put collateral
    adjusted_buying_power = snapshot.buying_power + adjusted_cash_balance - cash_secured_put_collateral
    
    # Debug output for calculations
    logger.warning("🔍 CASH/BUYING POWER DEBUG:")
    logger.warning(f"   Raw API Cash: ${snapshot.cash:,.2f}")
    logger.warning(f"   Raw API Buying Power: ${snapshot.buying_power:,.2f}")
    logger.warning(f"   Mutual Fund Value: ${total_mutual_fund_value:,.2f}")
    logger.warning(f"   Cash Secured Put Collateral: ${cash_secured_put_collateral:,.2f}")
    logger.warning(f"   → Adjusted Cash Balance: ${adjusted_cash_balance:,.2f}")
    logger.warning(f"   → Adjusted Buying Power: ${adjusted_buying_power:,.2f}")
    
    # Show essential info for quiet mode
    if logger.getEffectiveLevel() >= 40:  # ERROR level (quiet mode)
        # Only show the most important information
        logger.error(f"💰 Total Account Value: ${total_account_value:,.2f}")
        logger.error(f"💵 Cash Balance: ${adjusted_cash_balance:,.2f}")
        logger.error(f"💳 Buying Power: ${adjusted_buying_power:,.2f}")
    else:
        # Full display for normal and verbose modes
        logger.info("\n" + "="*60)
        logger.info("📊 ACCOUNT SNAPSHOT SUMMARY")
        logger.info("="*60)
        logger.info(f"Generated: {snapshot.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"💰 Cash Balance: ${adjusted_cash_balance:,.2f}")
        logger.info(f"💳 Buying Power: ${adjusted_buying_power:,.2f}")
        logger.info(f"📈 Total Stock Value: ${total_stock_value:,.2f}")
        logger.info(f"📉 Total Option Value: ${total_option_value:,.2f}")
        logger.info(f"💵 Total Mutual Fund Value: ${total_mutual_fund_value:,.2f}")
        
        # Show account value calculation details
        if snapshot.official_liquidation_value is not None:
            logger.info(f"🏦 TOTAL ACCOUNT VALUE: ${total_account_value:,.2f} (Schwab Official)")
            if abs(calculated_value - total_account_value) > 0.01:
                logger.debug(f"📊 Calculated Value: ${calculated_value:,.2f} (positions sum)")
                diff = calculated_value - total_account_value
                logger.debug(f"⚖️  Difference: ${diff:,.2f} (likely margin borrowing)")
        else:
            logger.info(f"🏦 TOTAL ACCOUNT VALUE: ${total_account_value:,.2f}")
        
        # Show position summary
        logger.info(f"\n📋 POSITIONS SUMMARY:")
        logger.info(f"   Stocks: {len(snapshot.stocks)} positions")
        logger.info(f"   Options: {len(snapshot.options)} positions")
        logger.info(f"   Mutual Funds: {len(snapshot.mutual_funds)} positions")
    
        # Show detailed positions only in normal/verbose mode
        if snapshot.stocks:
            logger.info(f"\n🔝 TOP STOCK POSITIONS:")
            sorted_stocks = sorted(snapshot.stocks, key=lambda x: abs(x.market_value), reverse=True)[:5]
            for i, stock in enumerate(sorted_stocks, 1):
                pnl_color = "🟢" if stock.pnl >= 0 else "🔴"
                logger.info(f"   {i}. {stock.symbol}: {stock.qty} shares @ ${stock.market_price:.2f} = ${stock.market_value:,.2f} {pnl_color} P&L: ${stock.pnl:,.2f}")
        
        if snapshot.options:
            logger.info(f"\n📊 OPTION POSITIONS:")
            for option in snapshot.options:
                pnl_color = "🟢" if option.pnl >= 0 else "🔴"
                logger.info(f"   {option.contract_symbol}: {option.qty} contracts @ ${option.market_price:.2f} = ${option.market_value:,.2f} {pnl_color} Total P&L: ${option.total_pnl:,.2f}")
        
        if snapshot.mutual_funds:
            logger.info(f"\n💵 MUTUAL FUND POSITIONS:")
            for fund in snapshot.mutual_funds:
                pnl_color = "🟢" if fund.pnl >= 0 else "🔴"
                description = f" ({fund.description})" if fund.description else ""
                logger.info(f"   {fund.symbol}{description}: {fund.qty:,.0f} shares @ ${fund.market_price:.2f} = ${fund.market_value:,.2f} {pnl_color} P&L: ${fund.pnl:,.2f}")
        
        logger.info("="*60)
    
    # Store tracking data
    _store_account_value_tracking(snapshot.generated_at, total_account_value, out_dir)
    
    # Run technical analysis if requested and we have a real client
    technicals_data = None
    if include_technicals and hasattr(client, 'client') and client.client is not None:
        try:
            logger.info("🔍 Running technical analysis...")
            technicals_data = analyze_account_technicals(client.client, snapshot)
            
            # Display technical signals in normal/verbose mode
            if logger.isEnabledFor(20):  # INFO level and above (not quiet mode)
                _display_technical_summary(technicals_data)
                
        except Exception as e:
            logger.warning(f"Technical analysis failed: {e}")
            logger.debug(f"Technical analysis error details: {e}", exc_info=True)
    
    payload = {
        "generated_at": snapshot.generated_at.isoformat(),
        "cash": str(snapshot.cash),
        "buying_power": str(snapshot.buying_power),
        "total_account_value": str(total_account_value),
        "stocks": [
            {
                "symbol": s.symbol,
                "qty": s.qty,
                "avg_cost": str(s.avg_cost),
                "market_price": str(s.market_price),
                "market_value": str(s.market_value),
                "pnl": str(s.pnl),
            }
            for s in snapshot.stocks
        ],
        "options": [
            {
                "symbol": o.symbol,
                "contract_symbol": o.contract_symbol,
                "qty": o.qty,
                "avg_cost": str(o.avg_cost),
                "market_price": str(o.market_price),
                "market_value": str(o.market_value),
                "pnl": str(o.pnl),
                "total_pnl": str(o.total_pnl),
                "strike": str(o.strike),
                "expiry": o.expiry.isoformat(),
                "put_call": o.put_call,
            }
            for o in snapshot.options
        ],
        "mutual_funds": [
            {
                "symbol": m.symbol,
                "qty": m.qty,
                "avg_cost": str(m.avg_cost),
                "market_price": str(m.market_price),
                "market_value": str(m.market_value),
                "pnl": str(m.pnl),
                "description": m.description,
            }
            for m in snapshot.mutual_funds
        ],
    }
    
    # Add technical analysis data if available
    if technicals_data:
        payload["technicals"] = technicals_data
    
    out_dir.mkdir(parents=True, exist_ok=True)
    output_file = out_dir / "account_snapshot.json"
    safe_write_json(output_file, payload)
    
    # Return both the data and the file path for programmatic access
    return {
        'data': payload,
        'file_path': output_file,
        'snapshot': snapshot,  # Original snapshot object
        'total_account_value': total_account_value,
        'adjusted_cash_balance': adjusted_cash_balance,
        'adjusted_buying_power': adjusted_buying_power
    }


def _display_technical_summary(technicals_data: dict):
    """Display a summary of technical analysis results."""
    logger = get_logger()
    
    logger.info("\n" + "="*60)
    logger.info("📊 TECHNICAL ANALYSIS SUMMARY")
    logger.info("="*60)
    
    # Stock technicals summary
    stocks = technicals_data.get("stocks", {})
    if stocks:
        logger.info(f"\n📈 STOCK POSITIONS ({len(stocks)} analyzed):")
        for symbol, data in stocks.items():
            if "error" in data:
                logger.info(f"   ❌ {symbol}: {data['error']}")
                continue
                
            signals = data.get("signals", [])
            rsi = data.get("indicators", {}).get("rsi")
            sma_20 = data.get("moving_averages", {}).get("sma_20")
            current_price = data.get("current_price")
            
            logger.info(f"\n   🔸 {symbol}: ${current_price:.2f}")
            if rsi:
                logger.info(f"      RSI: {rsi} {'🔴' if rsi > 70 else '🟢' if rsi < 30 else '🟡'}")
            if sma_20:
                trend = "↑" if current_price > sma_20 else "↓"
                logger.info(f"      20-MA: ${sma_20:.2f} {trend}")
            
            for signal in signals[:3]:  # Show top 3 signals
                logger.info(f"      {signal}")
    
    # Options technicals summary  
    options = technicals_data.get("options", {})
    if options:
        logger.info(f"\n📊 OPTION POSITIONS ({len(options)} analyzed):")
        for contract, data in options.items():
            if "error" in data:
                logger.info(f"   ❌ {contract}: {data['error']}")
                continue
                
            underlying = data.get("underlying_symbol")
            option_type = data.get("option_data", {}).get("option_type")
            strike = data.get("option_data", {}).get("strike")
            days_to_exp = data.get("option_data", {}).get("days_to_expiry")
            delta = data.get("greeks", {}).get("delta")
            pnl_pct = data.get("position_data", {}).get("pnl_pct")
            
            logger.info(f"\n   🔸 {underlying} {strike}{option_type} (Exp: {days_to_exp}d)")
            if delta:
                logger.info(f"      Delta: {delta:.3f}")
            if pnl_pct is not None:
                color = "🟢" if pnl_pct > 0 else "🔴"
                logger.info(f"      P&L: {pnl_pct:.1f}% {color}")
            
            signals = data.get("signals", [])
            for signal in signals[:2]:  # Show top 2 signals
                logger.info(f"      {signal}")
    
    summary = technicals_data.get("summary", {})
    logger.info(f"\n📋 Analysis completed: {summary.get('total_stocks_analyzed', 0)} stocks, {summary.get('total_options_analyzed', 0)} options")
    logger.info("="*60)


def _store_account_value_tracking(timestamp, total_value, out_dir: Path):
    """Store account value tracking data in a CSV file."""
    import csv
    from decimal import Decimal
    
    tracking_file = out_dir / "account_value_history.csv"
    
    # Check if file exists, if not create with headers
    file_exists = tracking_file.exists()
    
    with open(tracking_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        if not file_exists:
            writer.writerow(['timestamp', 'account_value', 'date', 'time'])
        
        # Write the current data
        writer.writerow([
            timestamp.isoformat(),
            f"{total_value:.2f}",
            timestamp.strftime('%Y-%m-%d'),
            timestamp.strftime('%H:%M:%S')
        ])
    
    print(f"💾 Account value tracking updated: {tracking_file}")
    
    # Show recent history (last 5 entries)
    _show_recent_history(tracking_file)


def _show_recent_history(tracking_file: Path):
    """Show recent account value history."""
    import csv
    
    try:
        with open(tracking_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        if len(rows) <= 1:
            return
            
        print(f"\n📈 RECENT ACCOUNT VALUE HISTORY:")
        recent_rows = rows[-5:] if len(rows) > 5 else rows
        
        for i, row in enumerate(recent_rows):
            date_str = row['date']
            time_str = row['time']
            value = float(row['account_value'])
            
            # Calculate change from previous
            change_str = ""
            if i > 0:
                prev_value = float(recent_rows[i-1]['account_value'])
                change = value - prev_value
                change_pct = (change / prev_value) * 100 if prev_value != 0 else 0
                color = "🟢" if change >= 0 else "🔴"
                change_str = f" {color} {change:+,.2f} ({change_pct:+.2f}%)"
            
            print(f"   {date_str} {time_str}: ${value:,.2f}{change_str}")
            
    except Exception as e:
        print(f"Could not read history: {e}")
