# Option Assignment Tracking System

A robust system for tracking and managing option assignments from broker transactions.

## Overview

This system automatically detects, records, and tracks option assignments with the following features:

- **Idempotent Processing**: Safe to run repeatedly without creating duplicates
- **Assignment Detection**: Recognizes various assignment transaction types
- **Basis Tracking**: Maintains assigned share basis for accurate P&L calculations
- **Historical Analysis**: Full assignment history with impact analysis
- **CLI Management**: Command-line tools for backfilling and monitoring

## Core Components

### 1. Database Layer (`utils/db_utils.py`)
- SQLite database with `assignments` and `assigned_basis` tables
- Idempotent upsert operations
- Transaction safety with automatic rollback

### 2. Assignment Processing (`utils/assignments.py`)
- Transaction type detection and filtering
- Option contract symbol parsing
- Event normalization from broker data
- Fallback ID generation for missing transaction IDs

### 3. CLI Management (`scripts/manage_assignments.py`)
- **backfill**: Historical assignment data retrieval
- **status**: Assignment statistics and summaries
- **ticker**: Individual ticker assignment analysis  
- **check**: Real-time assignment monitoring

### 4. Integration (`core/orchestrator.py`)
- Automatic assignment checking during account snapshots
- Non-blocking operation (won't crash main process)
- Warning alerts for new assignments

## Database Schema

### assignments table
```sql
CREATE TABLE assignments (
    id TEXT PRIMARY KEY,                -- Transaction ID or generated hash
    account_hash TEXT NOT NULL,         -- Account identifier
    option_symbol TEXT NOT NULL,        -- Full contract symbol
    ticker TEXT NOT NULL,               -- Underlying stock symbol
    contracts INTEGER NOT NULL,         -- Number of contracts assigned
    shares INTEGER NOT NULL,            -- Shares (contracts * 100)
    price_per_share REAL,               -- Assignment price per share
    total_amount REAL,                  -- Total assignment value
    assigned_at TEXT NOT NULL,          -- Assignment timestamp (ISO)
    transaction_type TEXT,              -- Broker transaction type
    related_order_id TEXT,              -- Related order if available
    raw_payload TEXT,                   -- Full broker event JSON
    recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### assigned_basis table
```sql
CREATE TABLE assigned_basis (
    ticker TEXT PRIMARY KEY,
    total_shares INTEGER DEFAULT 0,     -- Total assigned shares
    total_cost REAL DEFAULT 0.0,        -- Total cost basis
    avg_basis REAL DEFAULT 0.0,         -- Average cost per share
    last_assignment TEXT,               -- Last assignment timestamp
    assignment_count INTEGER DEFAULT 0  -- Number of assignments
);
```

## Usage Examples

### CLI Operations

```bash
# Check assignment status
python scripts/manage_assignments.py status --recent 7

# Show assignments for specific ticker
python scripts/manage_assignments.py ticker AAPL

# Backfill last 30 days
python scripts/manage_assignments.py backfill --days 30

# Check for new assignments
python scripts/manage_assignments.py check
```

### Programmatic Usage

```python
from utils.assignments import fetch_and_record_assignments
from utils.db_utils import AssignmentDB

# Initialize database
db = AssignmentDB()

# Fetch and record new assignments
assignments = fetch_and_record_assignments(client, db)

# Check assignment impact
from utils.assignments import get_assignment_impact_on_positions
impact = get_assignment_impact_on_positions('AAPL', db)
print(f"AAPL assigned shares: {impact['assigned_shares']}")
```

## Assignment Detection

The system recognizes these transaction types as assignments:
- `ASSIGNMENT`
- `EXERCISE` 
- `EXERCISE_ASSIGNMENT`
- `OPTION_ASSIGNMENT`
- `AUTO_EXERCISE`
- `EARLY_EXERCISE`
- `EXPIRATION_ASSIGNMENT`

Plus partial matches and description-based detection for maximum compatibility.

## Contract Symbol Parsing

Supports standard OCC format: `TICKER  YYMMDDCXXXXXXXX`

Example: `AAPL  231215C00150000`
- Ticker: `AAPL`
- Expiry: `2023-12-15`
- Type: `CALL` (C) or `PUT` (P)
- Strike: `150.00` (last 8 digits ÷ 1000)

## Error Handling

- **Network Errors**: Logged, returns empty list (non-blocking)
- **Parse Errors**: Individual transactions skipped, process continues
- **Missing Data**: Assignments recorded with null values where appropriate
- **Duplicate Events**: Handled via database constraints and idempotent operations

## Integration with Main System

Assignment checking is automatically integrated into the main account snapshot process:

```python
# In orchestrator.py
def run_once(client, out_dir=None, include_technicals=False, check_assignments=True):
    # ... get account snapshot ...
    
    if check_assignments:
        new_assignments = fetch_and_record_assignments(client, db)
        if new_assignments:
            logger.warning(f"🚨 {len(new_assignments)} NEW ASSIGNMENTS DETECTED")
```

## Testing

Comprehensive test suite covers:
- Assignment detection logic
- Contract symbol parsing
- Event normalization
- Database operations
- Idempotency
- Edge cases (missing data, duplicates, partial assignments)

```bash
# Run assignment tests
python -m pytest tests/test_assignments.py -v
```

## Future Enhancements

- Real-time assignment notifications (email/Slack)
- Assignment P&L impact analysis
- Integration with position reconciliation
- Advanced assignment forecasting based on Greeks
- Assignment tax reporting features