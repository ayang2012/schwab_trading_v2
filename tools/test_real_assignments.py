#!/usr/bin/env python3
"""Test assignment detection against real account transactions."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

try:
    from api.client import RealBrokerClient
    from utils.config_schwab import SchwabConfig
    from utils.logging import setup_logging
    from utils.assignments import (
        looks_like_assignment, normalize_assignment_event, normalize_schwab_assignment,
        fetch_and_record_assignments
    )
    from utils.db_utils import AssignmentDB
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)


def test_real_assignment_detection():
    """Test assignment detection against real account data."""
    logger = setup_logging(level='INFO')
    
    # Initialize client
    config = SchwabConfig.from_env()
    if not config.is_valid():
        config.app_key = "ER0kVS2P0U9WMMlRRt7Mw4ELCmVRwTB5"
        config.app_secret = "3mJejG1MBpISgcjj"
    
    try:
        client = RealBrokerClient(
            app_key=config.app_key,
            app_secret=config.app_secret,
            redirect_uri=config.redirect_uri,
            token_path=config.token_path
        )
        logger.info("✓ Schwab client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize client: {e}")
        return 1
    
    print("🔍 TESTING REAL ASSIGNMENT DETECTION")
    print("=" * 50)
    
    # Try to access the underlying schwabdev client
    if not hasattr(client, 'client') or client.client is None:
        print("❌ No underlying schwabdev client available")
        return 1
    
    schwab_client = client.client
    print(f"✓ Found underlying schwabdev client: {type(schwab_client)}")
    
    # Get account info
    try:
        accounts_response = schwab_client.account_linked()
        
        # Parse the response
        if hasattr(accounts_response, 'json'):
            accounts = accounts_response.json()
        else:
            accounts = accounts_response
            
        if not accounts:
            print("❌ No accounts found")
            return 1
        
        # Get first account
        first_account = accounts[0] if isinstance(accounts, list) else accounts
        account_hash = first_account.get('hashValue', 'unknown')
        account_number = first_account.get('accountNumber', 'unknown')
        print(f"✓ Using account: {account_number} (hash: {account_hash[:8]}...)")
        
    except Exception as e:
        print(f"❌ Failed to get account info: {e}")
        return 1
    
    # Try to fetch transactions
    print(f"\n📊 FETCHING TRANSACTIONS (Last 30 days)")
    
    try:
        # Calculate date range (Schwab API expects ISO format) - expand to 60 days for more data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)
        
        # Format dates for Schwab API
        start_date_str = start_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        end_date_str = end_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        
        print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} (60 days)")
        
        # Try different transaction methods
        transactions = None
        method_used = None
        
        # Method 1: account_transactions
        if hasattr(schwab_client, 'account_transactions'):
            try:
                print("Trying account_transactions method...")
                response = schwab_client.account_transactions(
                    account_hash, 
                    start_date_str,
                    end_date_str
                )
                if hasattr(response, 'json'):
                    transactions = response.json()
                else:
                    transactions = response
                method_used = "account_transactions"
            except Exception as e:
                print(f"  account_transactions failed: {e}")
        
        # Method 2: transactions with assignment-related types
        if not transactions and hasattr(schwab_client, 'transactions'):
            print("Trying transactions with assignment-related types...")
            all_transactions = []
            
            # Assignment-related transaction types in order of likelihood
            assignment_types = [
                'RECEIVE_AND_DELIVER',  # Most likely for assignments
                'TRADE',               # Regular trades (might include assignment exercises)
                'JOURNAL',             # Journal entries for assignments
                'CASH_RECEIPT',        # Cash from assignment
                'CASH_DISBURSEMENT'    # Cash for assignment
            ]
            
            for tx_type in assignment_types:
                try:
                    print(f"  Fetching {tx_type} transactions...")
                    response = schwab_client.transactions(
                        account_hash,
                        startDate=start_date_str,
                        endDate=end_date_str,
                        types=tx_type
                    )
                    
                    if response.status_code == 200:
                        tx_data = response.json() if hasattr(response, 'json') else response
                        if isinstance(tx_data, list) and tx_data:
                            print(f"    ✓ Found {len(tx_data)} {tx_type} transactions")
                            all_transactions.extend(tx_data)
                        else:
                            print(f"    - No {tx_type} transactions found")
                    else:
                        print(f"    - {tx_type} returned status {response.status_code}")
                        
                except Exception as e:
                    print(f"    - {tx_type} failed: {e}")
                    continue
            
            if all_transactions:
                transactions = all_transactions
                method_used = f"transactions (merged {len(assignment_types)} types)"
                print(f"  ✓ Total transactions collected: {len(transactions)}")
            else:
                print("  ❌ No assignment-related transactions found")
        
        # Method 3: Get transactions via account details
        if not transactions and hasattr(schwab_client, 'account_details'):
            try:
                print("Trying to get transactions via account details...")
                response = schwab_client.account_details(account_hash, fields='transactions')
                if hasattr(response, 'json'):
                    account_details = response.json()
                else:
                    account_details = response
                    
                if isinstance(account_details, dict):
                    transactions = account_details.get('transactions', [])
                    method_used = "account_details"
            except Exception as e:
                print(f"  account_details failed: {e}")
        
        if not transactions:
            print("❌ Could not fetch transactions with any method")
            print("\n🔧 Available methods on schwab client:")
            methods = [attr for attr in dir(schwab_client) if not attr.startswith('_')]
            for method in sorted(methods):
                if 'transaction' in method.lower() or 'trade' in method.lower():
                    print(f"  - {method}")
            return 1
        
        print(f"✅ Fetched transactions using: {method_used}")
        
        # Debug: check what type of data we got
        print(f"📊 Transaction data type: {type(transactions)}")
        
        if isinstance(transactions, str):
            # If it's a string, try to parse as JSON
            try:
                import json
                transactions = json.loads(transactions)
                print("✓ Parsed string as JSON")
            except:
                print("❌ Failed to parse transaction string as JSON")
                print(f"Raw data: {transactions[:200]}...")
                return 1
        
        # Check if transactions is a list or dict
        if isinstance(transactions, dict):
            # If it's a dict, look for transactions in common keys
            for key in ['transactions', 'data', 'results']:
                if key in transactions:
                    transactions = transactions[key]
                    print(f"✓ Found transactions in '{key}' field")
                    break
        
        print(f"📊 Total transactions found: {len(transactions) if isinstance(transactions, list) else 1}")
        
        # Ensure transactions is a list
        if not isinstance(transactions, list):
            transactions = [transactions]
        
    except Exception as e:
        print(f"❌ Failed to fetch transactions: {e}")
        return 1
    
    # Analyze transactions for assignments
    print(f"\n🔍 ANALYZING TRANSACTIONS FOR ASSIGNMENTS")
    print("-" * 40)
    
    assignment_candidates = []
    option_related = []
    all_transaction_types = set()
    
    for i, tx in enumerate(transactions):
        try:
            # Debug: Print first few transaction structures
            if i < 3:
                print(f"🔍 Transaction {i+1} structure:")
                import json
                print(json.dumps(tx, indent=2, default=str)[:400] + "...\n")
            
            # Get transaction type
            tx_type = tx.get('type', 'UNKNOWN')
            all_transaction_types.add(tx_type)
            
            # Check if option-related - look in transferItems
            symbol = ''
            is_option = False
            
            # Check main instrument
            instrument = tx.get('instrument', {})
            if instrument:
                symbol = instrument.get('symbol', '').upper()
                if any(keyword in symbol for keyword in ['PUT', 'CALL']) or len(symbol) > 6:
                    is_option = True
            
            # Also check transferItems for options
            transfer_items = tx.get('transferItems', [])
            for item in transfer_items:
                item_instrument = item.get('instrument', {})
                item_symbol = item_instrument.get('symbol', '').upper()
                if any(keyword in item_symbol for keyword in ['PUT', 'CALL']) or len(item_symbol) > 6:
                    is_option = True
                    if not symbol:  # Use first option symbol found
                        symbol = item_symbol
            
            if is_option:
                option_related.append(tx)
            
            # Check if looks like assignment (using description field for Schwab data)  
            description = tx.get('description', '').upper()
            if 'ASSIGNMENT' in description or ('REMOVED DUE TO ASSIGNMENT' in description):
                assignment_candidates.append(tx)
                print(f"  🎯 ASSIGNMENT FOUND: {description[:60]}...")
                
        except Exception as e:
            print(f"  Error analyzing transaction {i}: {e}")
            continue
    
    print(f"📈 Transaction types found: {sorted(all_transaction_types)}")
    print(f"📊 Option-related transactions: {len(option_related)}")
    print(f"🎯 Assignment candidates: {len(assignment_candidates)}")
    
    # Show option-related transactions
    if option_related:
        print(f"\n📊 OPTION-RELATED TRANSACTIONS:")
        for i, tx in enumerate(option_related[:10]):  # Show first 10
            tx_type = tx.get('transactionType', 'UNKNOWN')
            instrument = tx.get('instrument', {})
            symbol = instrument.get('symbol', 'N/A')
            qty = tx.get('quantity', 0)
            price = tx.get('price', tx.get('netAmount', 'N/A'))
            date = tx.get('transactionDate', tx.get('tradeDate', 'N/A'))
            
            assignment_marker = "🚨 ASSIGNMENT?" if looks_like_assignment(tx_type, tx) else ""
            
            print(f"  {i+1}. {tx_type} - {symbol}")
            print(f"      Qty: {qty}, Price: {price}, Date: {date}")
            print(f"      {assignment_marker}")
            print()
    
    # Test normalization on assignment candidates
    if assignment_candidates:
        print(f"🎯 TESTING ASSIGNMENT NORMALIZATION:")
        print("-" * 40)
        
        for i, tx in enumerate(assignment_candidates):
            print(f"\nCandidate {i+1}:")
            print(f"  Raw transaction: {tx}")
            
            try:
                normalized = normalize_schwab_assignment(tx, account_hash)
                if normalized:
                    print(f"  ✅ Successfully normalized:")
                    print(f"    Ticker: {normalized['ticker']}")
                    print(f"    Contracts: {normalized['contracts']}")
                    print(f"    Shares: {normalized['shares']}")
                    price_per_share = normalized['assignment_basis'] / normalized['shares'] if normalized['shares'] > 0 else 0
                    print(f"    Price: ${price_per_share:.2f} (Strike: ${normalized['strike_price']})")
                    print(f"    Date: {normalized['assignment_date'].strftime('%Y-%m-%d')}")
                else:
                    print(f"  ❌ Failed to normalize")
            except Exception as e:
                print(f"  ❌ Normalization error: {e}")
    
    # Try the full assignment detection system
    print(f"\n🚀 TESTING FULL ASSIGNMENT SYSTEM:")
    print("-" * 40)
    
    try:
        db = AssignmentDB('data/test_real_assignments.db')
        
        # We'll manually patch the client to return our fetched transactions
        class MockTransactionClient:
            def __init__(self, transactions, account_hash):
                self.transactions = transactions
                self.account_hash = account_hash
            
            def account_transactions(self, *args, **kwargs):
                return self.transactions
        
        mock_client = MockTransactionClient(transactions, account_hash)
        
        # Run assignment detection
        assignments = fetch_and_record_assignments(mock_client, db)
        
        if assignments:
            print(f"🎉 FOUND {len(assignments)} REAL ASSIGNMENTS!")
            for assignment in assignments:
                print(f"  📌 {assignment['ticker']}: {assignment['shares']} shares")
                print(f"     Contract: {assignment['option_symbol']}")
                price_per_share = assignment.get('assignment_basis', 0) / assignment.get('shares', 1) if assignment.get('shares', 0) > 0 else 0
                print(f"     Price: ${price_per_share:.2f} (Strike: ${assignment.get('strike_price', 0)})")
                print(f"     Date: {assignment.get('assignment_date', 'N/A')}")
                print()
        else:
            print("ℹ️  No assignments detected in the transaction data")
        
        # Show summary
        summary = db.get_assignment_summary()
        print(f"📊 FINAL SUMMARY:")
        print(f"  Total assignments recorded: {summary['total_assignments']}")
        if summary['assignments_by_ticker']:
            print(f"  Assignments by ticker:")
            for ticker_data in summary['assignments_by_ticker']:
                print(f"    {ticker_data['ticker']}: {ticker_data['count']} assignments")
        
    except Exception as e:
        print(f"❌ Full system test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n✅ Real assignment detection test completed!")
    return 0


if __name__ == "__main__":
    exit(test_real_assignment_detection())