"""Database utilities for assignment tracking and historical data."""

import sqlite3
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


class AssignmentDB:
    """Database handler for option assignment tracking."""
    
    def __init__(self, db_path: Union[str, Path] = "data/assignments.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
    
    def _init_schema(self):
        """Initialize database schema."""
        with self.get_connection() as conn:
            # Assignments table - stores each assignment event
            conn.execute("""
                CREATE TABLE IF NOT EXISTS assignments (
                    id TEXT PRIMARY KEY,                -- broker transaction id or stable hash
                    account_hash TEXT NOT NULL,         -- account identifier
                    option_symbol TEXT NOT NULL,        -- contract symbol (e.g., "AAPL  231215C00150000")
                    ticker TEXT NOT NULL,               -- underlying stock ticker
                    contracts INTEGER NOT NULL,         -- number of contracts assigned
                    shares INTEGER NOT NULL,            -- number of shares (usually contracts * 100)
                    price_per_share REAL,               -- assignment price per share
                    total_amount REAL,                  -- total assignment value
                    assigned_at TEXT NOT NULL,          -- assignment timestamp (ISO format)
                    transaction_type TEXT,              -- broker's transaction type
                    related_order_id TEXT,              -- related order if available
                    raw_payload TEXT,                   -- full broker event as JSON
                    recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(id)
                )
            """)
            
            # Assignment basis tracking - aggregates assigned shares per ticker
            conn.execute("""
                CREATE TABLE IF NOT EXISTS assigned_basis (
                    ticker TEXT PRIMARY KEY,
                    total_shares INTEGER DEFAULT 0,     -- total assigned shares
                    total_cost REAL DEFAULT 0.0,        -- total cost basis
                    avg_basis REAL DEFAULT 0.0,         -- average cost per share
                    last_assignment TEXT,               -- timestamp of last assignment
                    assignment_count INTEGER DEFAULT 0   -- number of assignments
                )
            """)
            
            # Indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_assignments_ticker ON assignments(ticker)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_assignments_assigned_at ON assignments(assigned_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_assignments_option_symbol ON assignments(option_symbol)")
    
    @contextmanager
    def get_connection(self):
        """Get database connection with automatic cleanup."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def upsert_assignment(self, assignment_dict: Dict[str, Any]) -> bool:
        """
        Idempotent insert/update of assignment record.
        
        Args:
            assignment_dict: Normalized assignment data
            
        Returns:
            True if new record was inserted, False if already existed
        """
        with self.get_connection() as conn:
            # Try to insert
            try:
                conn.execute("""
                    INSERT INTO assignments (
                        id, account_hash, option_symbol, ticker, contracts, shares,
                        price_per_share, total_amount, assigned_at, transaction_type,
                        related_order_id, raw_payload
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    assignment_dict['id'],
                    assignment_dict['account_hash'],
                    assignment_dict['option_symbol'],
                    assignment_dict['ticker'],
                    assignment_dict['contracts'],
                    assignment_dict['shares'],
                    assignment_dict.get('price_per_share'),
                    assignment_dict.get('total_amount'),
                    assignment_dict['assigned_at'],
                    assignment_dict.get('transaction_type'),
                    assignment_dict.get('related_order_id'),
                    json.dumps(assignment_dict.get('raw_payload', {}))
                ))
                return True
            except sqlite3.IntegrityError:
                # Record already exists, optionally update with new data
                logger.debug(f"Assignment {assignment_dict['id']} already exists")
                return False
    
    def record_assignment_basis(self, ticker: str, shares: int, price_per_share: float, 
                              assigned_at: str, metadata: Optional[Dict] = None):
        """
        Update assigned basis tracking for a ticker.
        
        Args:
            ticker: Stock symbol
            shares: Number of shares assigned
            price_per_share: Assignment price per share
            assigned_at: Assignment timestamp
            metadata: Additional metadata for logging
        """
        if price_per_share is None:
            logger.warning(f"Cannot update basis for {ticker}: price_per_share is None")
            return
        
        total_cost = shares * price_per_share
        
        with self.get_connection() as conn:
            # Get current basis or create new record
            cursor = conn.execute("SELECT * FROM assigned_basis WHERE ticker = ?", (ticker,))
            current = cursor.fetchone()
            
            if current:
                # Update existing record
                new_total_shares = current['total_shares'] + shares
                new_total_cost = current['total_cost'] + total_cost
                new_avg_basis = new_total_cost / new_total_shares if new_total_shares > 0 else 0
                new_count = current['assignment_count'] + 1
                
                conn.execute("""
                    UPDATE assigned_basis 
                    SET total_shares = ?, total_cost = ?, avg_basis = ?, 
                        last_assignment = ?, assignment_count = ?
                    WHERE ticker = ?
                """, (new_total_shares, new_total_cost, new_avg_basis, 
                      assigned_at, new_count, ticker))
            else:
                # Insert new record
                avg_basis = price_per_share
                conn.execute("""
                    INSERT INTO assigned_basis 
                    (ticker, total_shares, total_cost, avg_basis, last_assignment, assignment_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (ticker, shares, total_cost, avg_basis, assigned_at, 1))
            
            logger.info(f"Updated assigned basis for {ticker}: {shares} shares at ${price_per_share:.2f}")
    
    def get_assigned_shares(self, ticker: str) -> int:
        """Get total assigned shares for a ticker."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT total_shares FROM assigned_basis WHERE ticker = ?", (ticker,))
            row = cursor.fetchone()
            return row['total_shares'] if row else 0
    
    def get_assigned_basis(self, ticker: str) -> Optional[float]:
        """Get average assigned basis per share for a ticker."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT avg_basis FROM assigned_basis WHERE ticker = ?", (ticker,))
            row = cursor.fetchone()
            return row['avg_basis'] if row else None
    
    def get_assignments_for_ticker(self, ticker: str, limit: Optional[int] = None) -> List[Dict]:
        """Get assignment history for a ticker."""
        with self.get_connection() as conn:
            query = "SELECT * FROM assignments WHERE ticker = ? ORDER BY assigned_at DESC"
            if limit:
                query += f" LIMIT {limit}"
            
            cursor = conn.execute(query, (ticker,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_recent_assignments(self, days: int = 7) -> List[Dict]:
        """Get assignments from the last N days."""
        cutoff = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM assignments 
                WHERE assigned_at >= datetime(?, '-{} days')
                ORDER BY assigned_at DESC
            """.format(days), (cutoff,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_assignment_summary(self) -> Dict[str, Any]:
        """Get summary statistics of assignments."""
        with self.get_connection() as conn:
            # Total assignments
            cursor = conn.execute("SELECT COUNT(*) as total FROM assignments")
            total_assignments = cursor.fetchone()['total']
            
            # Assignments by ticker
            cursor = conn.execute("""
                SELECT ticker, COUNT(*) as count, SUM(shares) as total_shares
                FROM assignments 
                GROUP BY ticker 
                ORDER BY count DESC
            """)
            by_ticker = [dict(row) for row in cursor.fetchall()]
            
            # Recent activity (last 30 days)
            cursor = conn.execute("""
                SELECT COUNT(*) as recent_count
                FROM assignments 
                WHERE assigned_at >= datetime('now', '-30 days')
            """)
            recent_assignments = cursor.fetchone()['recent_count']
            
            return {
                'total_assignments': total_assignments,
                'recent_assignments_30d': recent_assignments,
                'assignments_by_ticker': by_ticker
            }


def generate_assignment_id(option_symbol: str, contracts: int, assigned_at: str, 
                          price_per_share: Optional[float], account_hash: str) -> str:
    """
    Generate a stable ID for assignment when broker doesn't provide one.
    
    Args:
        option_symbol: Contract symbol
        contracts: Number of contracts
        assigned_at: Assignment timestamp
        price_per_share: Price per share (can be None)
        account_hash: Account identifier
        
    Returns:
        Stable hash ID for the assignment
    """
    # Create deterministic hash from assignment details
    content = f"{account_hash}|{option_symbol}|{contracts}|{assigned_at}|{price_per_share or 'NULL'}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# Convenience function for backward compatibility
def get_db(db_path: Union[str, Path] = "data/assignments.db") -> AssignmentDB:
    """Get AssignmentDB instance."""
    return AssignmentDB(db_path)