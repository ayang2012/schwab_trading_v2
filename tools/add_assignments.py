#!/usr/bin/env python3
"""Add sample assignments based on detected data."""

import sys
import os
import sqlite3
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def add_sample_assignments():
    """Add the 7 assignments we detected in testing."""
    
    # Sample assignments from your account (based on test results)
    assignments = [
        {
            'assignment_id': 'crm_put_250_20250815_assignment',
            'transaction_id': '101313951071',
            'account_hash': 'D97AD8F0',
            'ticker': 'CRM',
            'option_symbol': 'CRM   250815P00250000',
            'option_type': 'put',
            'strike_price': 250.0,
            'contracts': 1,
            'shares': 100,
            'assignment_date': '2025-08-15T04:00:00+00:00',
            'assignment_type': 'assignment',
            'assignment_basis': 25000.0
        },
        {
            'assignment_id': 'amzn_put_227.5_20250926_assignment',
            'transaction_id': '103683919248',
            'account_hash': 'D97AD8F0',
            'ticker': 'AMZN',
            'option_symbol': 'AMZN  250926P00227500',
            'option_type': 'put',
            'strike_price': 227.5,
            'contracts': 1,
            'shares': 100,
            'assignment_date': '2025-09-26T04:00:00+00:00',
            'assignment_type': 'assignment',
            'assignment_basis': 22750.0
        },
        {
            'assignment_id': 'sofi_put_29_20250926_assignment',
            'transaction_id': '103683919243',
            'account_hash': 'D97AD8F0',
            'ticker': 'SOFI',
            'option_symbol': 'SOFI  250926P00029000',
            'option_type': 'put',
            'strike_price': 29.0,
            'contracts': 3,
            'shares': 300,
            'assignment_date': '2025-09-26T04:00:00+00:00',
            'assignment_type': 'assignment',
            'assignment_basis': 8700.0
        },
        {
            'assignment_id': 'aal_put_12_20250926_assignment',
            'transaction_id': '103683919246',
            'account_hash': 'D97AD8F0',
            'ticker': 'AAL',
            'option_symbol': 'AAL   250926P00012000',
            'option_type': 'put',
            'strike_price': 12.0,
            'contracts': 20,
            'shares': 2000,
            'assignment_date': '2025-09-26T04:00:00+00:00',
            'assignment_type': 'assignment',
            'assignment_basis': 24000.0
        },
        {
            'assignment_id': 'aal_put_12.5_20250926_assignment',
            'transaction_id': '103683919244',
            'account_hash': 'D97AD8F0',
            'ticker': 'AAL',
            'option_symbol': 'AAL   250926P00012500',
            'option_type': 'put',
            'strike_price': 12.5,
            'contracts': 5,
            'shares': 500,
            'assignment_date': '2025-09-26T04:00:00+00:00',
            'assignment_type': 'assignment',
            'assignment_basis': 6250.0
        },
        {
            'assignment_id': 'aal_put_12.5_20250919_assignment',
            'transaction_id': '103252499876',
            'account_hash': 'D97AD8F0',
            'ticker': 'AAL',
            'option_symbol': 'AAL   250919P00012500',
            'option_type': 'put',
            'strike_price': 12.5,
            'contracts': 65,
            'shares': 6500,
            'assignment_date': '2025-09-19T04:00:00+00:00',
            'assignment_type': 'assignment',
            'assignment_basis': 81250.0
        },
        {
            'assignment_id': 'tsm_call_247.5_20250912_assignment',
            'transaction_id': '102834171098',
            'account_hash': 'D97AD8F0',
            'ticker': 'TSM',
            'option_symbol': 'TSM   250912C00247500',
            'option_type': 'call',
            'strike_price': 247.5,
            'contracts': 1,
            'shares': 100,
            'assignment_date': '2025-09-12T04:00:00+00:00',
            'assignment_type': 'assignment',
            'assignment_basis': 24750.0
        }
    ]
    
    db_path = "data/assignments.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print(f"📊 Adding {len(assignments)} assignments to database...")
        
        for assignment in assignments:
            cursor.execute("""
                INSERT OR REPLACE INTO assignments 
                (id, account_hash, option_symbol, ticker, contracts, shares,
                 price_per_share, total_amount, assigned_at, transaction_type, raw_payload)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                assignment['transaction_id'],
                assignment['account_hash'],
                assignment['option_symbol'],
                assignment['ticker'],
                assignment['contracts'],
                assignment['shares'],
                assignment['strike_price'],  # price per share is strike price for assignments
                assignment['assignment_basis'],  # total amount
                assignment['assignment_date'],
                assignment['assignment_type'],
                '{}',  # empty raw payload for now
            ))
            print(f"  ✅ {assignment['ticker']} {assignment['option_type'].upper()} @ ${assignment['strike_price']} ({assignment['contracts']} contracts)")
        
        conn.commit()
        conn.close()
        
        print(f"\n✅ Successfully added {len(assignments)} assignments!")
        print("\n📊 To view assignments, run:")
        print("  python3.11 view_assignments.py")
        print("  python3.11 scripts/manage_assignments.py status")
        
    except Exception as e:
        print(f"❌ Error adding assignments: {e}")

if __name__ == "__main__":
    add_sample_assignments()