# Testing Safety Guidelines

## 🛡️ Production Data Protection

This project now includes comprehensive safety measures to prevent accidental modification of production data during testing and development.

## Safe Testing Practices

### 1. **Always Use Isolated Environments for Testing**

```python
# ✅ SAFE - Uses isolated test environment
from tests.test_utils import isolated_test_environment

with isolated_test_environment() as test_env:
    db = test_env.get_test_db()
    # Do testing here - production data never touched

# ❌ DANGEROUS - Directly uses production database
from utils.db_utils import AssignmentDB
db = AssignmentDB("data/assignments.db")  # This affects real data!
```

### 2. **Use the Safe Testing Script**

```bash
# ✅ SAFE - Demonstrates functionality without affecting production data
python3.11 scripts/safe_testing.py

# ❌ DANGEROUS - Manual testing that could affect production
python3.11 -c "from utils.db_utils import AssignmentDB; ..."
```

### 3. **Enable Test Mode for Development**

```bash
# Set test mode environment variable
export SCHWAB_TEST_MODE=1

# Or prefix individual commands
SCHWAB_TEST_MODE=1 python3.11 your_script.py
```

## Safety Features

### Automatic Detection
- Tests are automatically detected when run via pytest
- Test files (containing `test_` or in `/tests/` directory) are auto-detected
- `SCHWAB_TEST_MODE` environment variable can force test mode

### Production Warnings
- Warnings displayed when accessing production database outside tests
- Confirmation required for potentially dangerous operations
- Clear indication of test vs production mode

### Isolated Test Infrastructure

#### `isolated_test_environment()` Context Manager
- Creates temporary directories and databases
- Automatically cleans up after testing
- Guarantees no production data contamination

#### Safety Utilities
- `ensure_not_production_db()` - Validates database paths
- `verify_test_isolation()` - Checks for production file conflicts
- Pre-built test data generators for consistent testing

## Example: Safe CALL/PUT Testing

```python
# ✅ SAFE approach
from tests.test_utils import isolated_test_environment

with isolated_test_environment() as test_env:
    db = test_env.get_test_db()
    
    # Test PUT assignment
    db.record_assignment_basis('XYZ', 200, 50.0, '2024-01-15', 'PUT')
    
    # Test CALL assignment  
    db.record_assignment_basis('XYZ', 100, 55.0, '2024-02-15', 'CALL')
    
    # Check results - no production data affected!
    # Environment automatically cleaned up
```

## Commands Reference

### Safe Testing Commands
```bash
# Run all tests safely
python3.11 -m pytest tests/

# Run safe demonstrations
python3.11 scripts/safe_testing.py

# Check test environment status
python3.11 tests/test_utils.py

# Enable test mode
export SCHWAB_TEST_MODE=1
```

### Production Commands (Use with Caution)
```bash
# View assignment status (read-only, safe)
python3.11 scripts/manage_assignments.py status

# View specific ticker (read-only, safe) 
python3.11 scripts/manage_assignments.py ticker AAPL

# Check for new assignments (writes to database - be careful!)
python3.11 scripts/manage_assignments.py check
```

## Key Principles

1. **Default to Safety**: Production data is protected by default
2. **Explicit Consent**: Dangerous operations require confirmation
3. **Clear Separation**: Test and production environments are clearly distinguished
4. **Automatic Cleanup**: Test environments self-destruct to prevent contamination
5. **Comprehensive Warnings**: Clear indicators when production data is at risk

## If You Accidentally Affect Production Data

The production database is backed up regularly, but if you accidentally modify it:

1. **Stop immediately** - Don't make more changes
2. **Check git history** for any recent database commits
3. **Use the backfill commands** to restore from real Schwab data:
   ```bash
   python3.11 scripts/manage_assignments.py backfill --days 90
   ```
4. **Consider restoring from backup** if available

Remember: **When in doubt, use test mode!** 🛡️