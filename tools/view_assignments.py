#!/usr/bin/env python3
"""Simple script to view assignments from database."""

import sys
import os
import sqlite3
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def view_assignments(db_path="data/assignments.db"):
    """View assignments from database."""
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"📊 Database tables: {[t[0] for t in tables]}")
        
        # Get assignment count
        cursor.execute("SELECT COUNT(*) FROM assignments")
        count = cursor.fetchone()[0]
        print(f"📈 Total assignments: {count}")
        
        if count == 0:
            print("ℹ️  No assignments found in database")
            return
        
        # Get all assignments
        cursor.execute("""
            SELECT ticker, option_symbol, price_per_share, contracts, shares, 
                   assigned_at, total_amount, id
            FROM assignments 
            ORDER BY assigned_at DESC
        """)
        
        assignments = cursor.fetchall()
        
        print(f"\n🎯 ASSIGNMENTS FOUND ({len(assignments)}):")
        print("=" * 80)
        
        total_shares = 0
        total_basis = 0
        
        for i, (ticker, option_symbol, price_per_share, contracts, shares, date, total_amount, transaction_id) in enumerate(assignments, 1):
            # Extract option type from symbol
            option_type = "CALL" if "C" in option_symbol[-9:] else "PUT"
            print(f"{i}. {ticker} {option_type} @ ${price_per_share}")
            print(f"   📅 Date: {date[:10]}")
            print(f"   📊 Contracts: {contracts} ({shares} shares)")
            print(f"   💰 Total Value: ${total_amount:,.2f}")
            print(f"   🆔 Symbol: {option_symbol}")
            print()
            
            total_shares += shares
            total_basis += total_amount
        
        print("=" * 80)
        print(f"📊 SUMMARY:")
        print(f"   Total Assignments: {len(assignments)}")
        print(f"   Total Shares: {total_shares:,}")
        print(f"   Total Assignment Basis: ${total_basis:,.2f}")
        
        # Show by ticker
        cursor.execute("""
            SELECT ticker, SUM(shares), SUM(total_amount), COUNT(*)
            FROM assignments 
            GROUP BY ticker 
            ORDER BY SUM(shares) DESC
        """)
        
        ticker_summary = cursor.fetchall()
        print(f"\n📈 BY TICKER:")
        for ticker, shares, basis, count in ticker_summary:
            avg_price = basis / shares if shares > 0 else 0
            print(f"   {ticker}: {shares:,} shares (${avg_price:.2f} avg) from {count} assignments")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error reading database: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="View assignment data")
    parser.add_argument("--db", default="data/assignments.db", help="Database path")
    args = parser.parse_args()
    
    view_assignments(args.db)