#!/usr/bin/env python3
"""Quick script to populate assignment database with detected assignments."""

import sys
import os
from datetime import datetime, timezone, timedelta

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from api.client import RealBrokerClient
    from utils.config_schwab import SchwabConfig
    from utils.logging import setup_logging
    from utils.assignments import normalize_schwab_assignment
    from utils.db_utils import AssignmentDB
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

def main():
    setup_logging()
    
    # Initialize Schwab client (copying exact logic from test script)
    config = SchwabConfig()
    
    try:
        import schwabdev
        client = schwabdev.Client(
            app_key=config.app_key,
            app_secret=config.app_secret,
            callback_url=config.redirect_uri,
            tokens_file=config.token_path
        )
        print("✓ Schwab client initialized successfully")
    except Exception as e:
        print(f"Failed to initialize client: {e}")
        return 1
    
    schwab_client = client
    
    # Get account info
    accounts_response = schwab_client.account_linked()
    accounts = accounts_response.json() if hasattr(accounts_response, 'json') else accounts_response
    account_hash = accounts[0].get('hashValue', 'unknown')
    
    print(f"📊 Populating assignments for account: {account_hash[:8]}...")
    
    # Fetch transactions from last 60 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)
    start_date_str = start_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')
    end_date_str = end_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')
    
    # Get assignment-related transactions
    assignment_types = ['RECEIVE_AND_DELIVER', 'TRADE', 'JOURNAL']
    all_transactions = []
    
    for tx_type in assignment_types:
        try:
            response = schwab_client.transactions(
                account_hash,
                startDate=start_date_str,
                endDate=end_date_str,
                types=tx_type
            )
            
            if response.status_code == 200:
                tx_data = response.json() if hasattr(response, 'json') else response
                if isinstance(tx_data, list) and tx_data:
                    all_transactions.extend(tx_data)
                    print(f"  ✓ Found {len(tx_data)} {tx_type} transactions")
        except Exception as e:
            print(f"  - {tx_type} failed: {e}")
    
    print(f"\n🔍 Analyzing {len(all_transactions)} transactions for assignments...")
    
    # Find assignments
    assignments = []
    for tx in all_transactions:
        description = tx.get('description', '').upper()
        if 'ASSIGNMENT' in description or ('REMOVED DUE TO ASSIGNMENT' in description):
            assignments.append(tx)
    
    print(f"🎯 Found {len(assignments)} assignment transactions")
    
    # Initialize database
    db = AssignmentDB()
    
    # Process and store assignments
    stored_count = 0
    for tx in assignments:
        try:
            normalized = normalize_schwab_assignment(tx, account_hash)
            if normalized:
                # Store in database
                result = db.upsert_assignment(normalized)
                if result:
                    print(f"  ✅ Stored: {normalized['ticker']} {normalized['option_type'].upper()} @ ${normalized['strike_price']} ({normalized['contracts']} contracts)")
                    stored_count += 1
                else:
                    print(f"  ⚠️  Duplicate: {normalized['assignment_id']}")
        except Exception as e:
            print(f"  ❌ Failed to process assignment: {e}")
    
    print(f"\n✅ Successfully stored {stored_count} assignments in database!")
    print("\n📊 To view assignments, run:")
    print("  python3.11 scripts/manage_assignments.py status")
    print("  python3.11 scripts/manage_assignments.py ticker AAL")

if __name__ == "__main__":
    main()