"""Option assignment detection and recording system."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union
import re

from utils.db_utils import AssignmentDB, generate_assignment_id

logger = logging.getLogger(__name__)


def looks_like_assignment(transaction_type: str, transaction_data: Dict[str, Any]) -> bool:
    """
    Detect if a transaction represents an option assignment.
    
    Args:
        transaction_type: Broker's transaction type string
        transaction_data: Full transaction data
        
    Returns:
        True if this looks like an assignment event
    """
    if not transaction_type:
        return False
    
    # Common assignment transaction types from brokers
    assignment_types = {
        'ASSIGNMENT', 'EXERCISE', 'EXERCISE_ASSIGNMENT', 'OPTION_ASSIGNMENT',
        'AUTO_EXERCISE', 'EARLY_EXERCISE', 'EXPIRATION_ASSIGNMENT',
        'ASSIGNED', 'EXERCISED'
    }
    
    transaction_type_upper = transaction_type.upper()
    
    # Direct match
    if transaction_type_upper in assignment_types:
        return True
    
    # Partial match for complex type strings
    for assignment_type in assignment_types:
        if assignment_type in transaction_type_upper:
            return True
    
    # Check description field as fallback
    description = transaction_data.get('description', '').upper()
    if any(keyword in description for keyword in ['ASSIGNED', 'EXERCISED', 'EXERCISE']):
        return True
    
    return False


def extract_option_details(option_symbol: str) -> Optional[Dict[str, Any]]:
    """
    Extract details from option contract symbol.
    
    Args:
        option_symbol: Option contract symbol (e.g., "AAPL  231215C00150000")
        
    Returns:
        Dict with ticker, expiry, option_type, strike or None if parsing fails
    """
    # Standard OCC format: TICKER  YYMMDDCXXXXXXXX or TICKER  YYMMDDPXXXXXXXX
    # Where C/P is call/put, and XXXXXXXX is strike * 1000
    
    if not option_symbol or len(option_symbol) < 15:
        return None
    
    try:
        # Extract ticker (first 6 chars, stripped)
        ticker = option_symbol[:6].strip()
        
        # Extract date part (positions 6-11: YYMMDD)
        date_str = option_symbol[6:12]
        
        # Extract option type (position 12: C or P)
        option_type = option_symbol[12]
        if option_type not in ['C', 'P']:
            return None
        
        # Extract strike (last 8 digits, divide by 1000)
        strike_str = option_symbol[13:21]
        strike = float(strike_str) / 1000.0
        
        # Parse expiry date
        year = 2000 + int(date_str[:2])
        month = int(date_str[2:4])
        day = int(date_str[4:6])
        expiry = datetime(year, month, day).date()
        
        return {
            'ticker': ticker,
            'expiry': expiry,
            'option_type': 'CALL' if option_type == 'C' else 'PUT',
            'strike': strike
        }
    except (ValueError, IndexError) as e:
        logger.warning(f"Failed to parse option symbol '{option_symbol}': {e}")
        return None


def normalize_schwab_assignment(transaction: Dict[str, Any], account_hash: str) -> Optional[Dict[str, Any]]:
    """
    Normalize a Schwab transaction into a standard assignment record.
    
    Args:
        transaction: Raw Schwab transaction data
        account_hash: Account identifier
        
    Returns:
        Normalized assignment dict or None if normalization fails
    """
    try:
        # Extract transaction ID
        transaction_id = str(transaction.get('activityId', ''))
        if not transaction_id:
            logger.warning("Schwab assignment missing activityId")
            return None
        
        # Get assignment info from transferItems
        transfer_items = transaction.get('transferItems', [])
        if not transfer_items:
            logger.warning("Schwab assignment missing transferItems")
            return None
        
        # Find the option instrument
        option_item = None
        for item in transfer_items:
            instrument = item.get('instrument', {})
            if instrument.get('assetType') == 'OPTION':
                option_item = item
                break
        
        if not option_item:
            logger.warning("No option instrument found in transferItems")
            return None
        
        instrument = option_item['instrument']
        option_symbol = instrument.get('symbol', '')
        
        if not option_symbol:
            logger.warning("Option instrument missing symbol")
            return None
        
        # Extract option details from Schwab data
        underlying_symbol = instrument.get('underlyingSymbol', '')
        put_call = instrument.get('putCall', '').upper()
        strike_price = float(instrument.get('strikePrice', 0))
        expiration_date = instrument.get('expirationDate', '')
        
        # Parse expiration date
        assignment_date = None
        if expiration_date:
            try:
                assignment_date = datetime.fromisoformat(expiration_date.replace('Z', '+00:00'))
            except:
                pass
        
        if not assignment_date:
            # Fallback to trade date
            trade_date = transaction.get('tradeDate', '')
            if trade_date:
                try:
                    assignment_date = datetime.fromisoformat(trade_date.replace('Z', '+00:00'))
                except:
                    pass
        
        if not assignment_date:
            assignment_date = datetime.now(timezone.utc)
        
        # Get quantity from amount field (this is contracts, not shares)
        contracts = abs(float(option_item.get('amount', 0)))
        if contracts == 0:
            logger.warning("Assignment has zero contracts")
            return None
        
        # Extract assignment type from description
        description = transaction.get('description', '').upper()
        is_exercise = 'EXERCISE' in description
        is_assignment = 'ASSIGNMENT' in description
        
        assignment_type = 'exercise' if is_exercise else 'assignment'
        
        # Calculate shares (100 shares per contract)
        shares = int(contracts * 100)
        
        # Calculate assignment basis (strike price * shares)
        assignment_basis = strike_price * shares
        
        # Generate assignment ID
        assignment_id = generate_assignment_id(
            underlying_symbol, put_call.lower(), strike_price, 
            assignment_date.strftime('%Y%m%d'), assignment_type
        )
        
        normalized = {
            'assignment_id': assignment_id,
            'transaction_id': transaction_id,
            'account_hash': account_hash,
            'ticker': underlying_symbol,
            'option_symbol': option_symbol,
            'option_type': put_call.lower(),
            'strike_price': strike_price,
            'contracts': int(contracts),
            'shares': shares,
            'assignment_date': assignment_date,
            'assignment_type': assignment_type,
            'assignment_basis': assignment_basis,
            'raw_transaction': transaction
        }
        
        logger.info(f"✓ Normalized Schwab assignment: {assignment_id}")
        return normalized
        
    except Exception as e:
        logger.error(f"Failed to normalize Schwab assignment: {e}")
        return None


def normalize_assignment_event(transaction: Dict[str, Any], account_hash: str) -> Optional[Dict[str, Any]]:
    """
    Normalize a broker transaction into a standard assignment record.
    
    Args:
        transaction: Raw transaction data from broker
        account_hash: Account identifier
        
    Returns:
        Normalized assignment dict or None if normalization fails
    """
    try:
        # Extract transaction ID (prefer broker ID, fallback to generated)
        transaction_id = transaction.get('transactionId') or transaction.get('id')
        
        # Extract transaction type
        transaction_type = (transaction.get('transactionType') or 
                          transaction.get('type') or '').strip()
        
        # Extract instrument info
        instrument = transaction.get('instrument', {})
        option_symbol = instrument.get('symbol') or transaction.get('symbol', '')
        
        if not option_symbol:
            logger.warning("Assignment event missing option symbol")
            return None
        
        # Parse option details
        option_details = extract_option_details(option_symbol)
        if not option_details:
            logger.warning(f"Could not parse option symbol: {option_symbol}")
            return None
        
        ticker = option_details['ticker']
        
        # Extract quantities
        # Some brokers use 'quantity', others use 'longQuantity'/'shortQuantity'
        quantity = transaction.get('quantity', 0)
        if quantity == 0:
            long_qty = transaction.get('longQuantity', 0)
            short_qty = transaction.get('shortQuantity', 0)
            quantity = long_qty - short_qty
        
        if quantity == 0:
            logger.warning("Assignment event has zero quantity")
            return None
        
        # For assignments, quantity might be in shares or contracts
        # If quantity looks like shares (e.g., 100, 200), convert to contracts
        if abs(quantity) % 100 == 0 and abs(quantity) >= 100:
            contracts = abs(quantity) // 100
            shares = abs(quantity)
        else:
            # Assume quantity is in contracts
            contracts = abs(quantity)
            shares = contracts * 100
        
        # Extract price
        price_per_share = None
        for price_field in ['price', 'netAmount', 'executionPrice', 'averagePrice']:
            if price_field in transaction:
                raw_price = transaction[price_field]
                if raw_price is not None:
                    if price_field == 'netAmount':
                        # netAmount might be total, divide by shares
                        price_per_share = abs(float(raw_price)) / shares if shares > 0 else None
                    else:
                        price_per_share = abs(float(raw_price))
                    break
        
        # Extract timestamp
        assigned_at = None
        for time_field in ['transactionDate', 'tradeDate', 'executionTime', 'settlementDate']:
            if time_field in transaction:
                time_value = transaction[time_field]
                if time_value:
                    try:
                        # Handle various timestamp formats
                        if isinstance(time_value, str):
                            if 'T' in time_value:
                                assigned_at = datetime.fromisoformat(time_value.replace('Z', '+00:00'))
                            else:
                                assigned_at = datetime.strptime(time_value, '%Y-%m-%d')
                        else:
                            assigned_at = datetime.fromtimestamp(time_value, tz=timezone.utc)
                        break
                    except (ValueError, TypeError):
                        continue
        
        if not assigned_at:
            # Fallback to current time
            assigned_at = datetime.now(timezone.utc)
            logger.warning("Assignment event missing timestamp, using current time")
        
        # Ensure timezone-aware
        if assigned_at.tzinfo is None:
            assigned_at = assigned_at.replace(tzinfo=timezone.utc)
        
        # Generate ID if not provided
        if not transaction_id:
            transaction_id = generate_assignment_id(
                option_symbol, contracts, assigned_at.isoformat(), 
                price_per_share, account_hash
            )
        
        # Calculate total amount
        total_amount = None
        if price_per_share is not None:
            total_amount = shares * price_per_share
        
        # Build normalized record
        normalized = {
            'id': str(transaction_id),
            'account_hash': account_hash,
            'option_symbol': option_symbol,
            'ticker': ticker,
            'option_type': option_details['option_type'],
            'contracts': contracts,
            'shares': shares,
            'price_per_share': price_per_share,
            'total_amount': total_amount,
            'assigned_at': assigned_at.isoformat(),
            'transaction_type': transaction_type,
            'related_order_id': transaction.get('orderId') or transaction.get('relatedOrderId'),
            'raw_payload': transaction
        }
        
        return normalized
        
    except Exception as e:
        logger.error(f"Error normalizing assignment event: {e}")
        logger.debug(f"Raw transaction: {transaction}")
        return None


def fetch_and_record_assignments(
    client, 
    db: Union[AssignmentDB, str, None] = None,
    since: Optional[datetime] = None,
    lookback_days: int = 7
) -> List[Dict[str, Any]]:
    """
    Fetch assignment events from broker and record them in database.
    
    Args:
        client: Broker client (should have account_transactions method)
        db: Database instance or path, defaults to standard location
        since: Fetch transactions since this timestamp
        lookback_days: Days to look back if since is None
        
    Returns:
        List of recorded assignment records
    """
    if isinstance(db, str) or db is None:
        db = AssignmentDB(db or "data/assignments.db")
    
    recorded = []
    
    try:
        # Determine time window
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        
        # Ensure timezone aware
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        
        # Get account info
        account_hash = getattr(client, 'account_hash', 'default')
        
        # Fetch transactions
        # Note: This assumes client has an account_transactions method
        # We'll need to adapt this based on actual Schwab client interface
        try:
            if hasattr(client, 'account_transactions'):
                transactions = client.account_transactions(
                    from_date=since.date(),
                    to_date=datetime.now(timezone.utc).date()
                )
            elif hasattr(client, 'client') and hasattr(client.client, 'account_transactions'):
                # Handle wrapped client
                transactions = client.client.account_transactions(
                    from_date=since.date(),
                    to_date=datetime.now(timezone.utc).date()
                )
            else:
                logger.warning("Client does not support transaction fetching")
                return recorded
                
        except Exception as e:
            logger.error(f"Failed to fetch transactions: {e}")
            return recorded
        
        if not transactions:
            logger.debug("No transactions returned from broker")
            return recorded
        
        # Process each transaction
        for tx in transactions:
            try:
                # Check if this looks like an assignment
                tx_type = tx.get('transactionType') or tx.get('type', '')
                if not looks_like_assignment(tx_type, tx):
                    continue
                
                # Normalize the event
                normalized = normalize_assignment_event(tx, account_hash)
                if not normalized:
                    continue
                
                # Record in database (idempotent)
                was_inserted = db.upsert_assignment(normalized)
                if was_inserted:
                    # Update basis tracking
                    if normalized['price_per_share'] is not None:
                        db.record_assignment_basis(
                            normalized['ticker'],
                            normalized['shares'],
                            normalized['price_per_share'],
                            normalized['assigned_at'],
                            normalized.get('option_type', 'PUT'),  # Default to PUT if missing
                            {'assignment_id': normalized['id']}
                        )
                    
                    price_str = f"${normalized['price_per_share']:.2f}" if normalized['price_per_share'] is not None else "TBD"
                    logger.info(
                        f"Recorded assignment {normalized['id']}: "
                        f"{normalized['shares']} shares of {normalized['ticker']} "
                        f"at {price_str}"
                    )
                    recorded.append(normalized)
                else:
                    logger.debug(f"Assignment {normalized['id']} already recorded")
                    
            except Exception as e:
                logger.error(f"Error processing transaction: {e}")
                logger.debug(f"Problematic transaction: {tx}")
                continue
        
        logger.info(f"Processed {len(transactions)} transactions, recorded {len(recorded)} new assignments")
        
    except Exception as e:
        logger.error(f"Error in fetch_and_record_assignments: {e}")
    
    return recorded


def get_assignment_impact_on_positions(ticker: str, db: Optional[AssignmentDB] = None) -> Dict[str, Any]:
    """
    Get the impact of assignments on current positions for a ticker.
    
    Args:
        ticker: Stock symbol
        db: Database instance
        
    Returns:
        Dict with assignment impact information
    """
    if db is None:
        db = AssignmentDB()
    
    assigned_shares = db.get_assigned_shares(ticker)
    assigned_basis = db.get_assigned_basis(ticker)
    recent_assignments = db.get_assignments_for_ticker(ticker, limit=10)
    
    return {
        'ticker': ticker,
        'assigned_shares': assigned_shares,
        'assigned_basis': assigned_basis,
        'total_assigned_cost': assigned_shares * assigned_basis if assigned_basis else 0,
        'recent_assignments': recent_assignments,
        'assignment_count': len(recent_assignments)
    }