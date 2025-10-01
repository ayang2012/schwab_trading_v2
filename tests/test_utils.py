"""Testing utilities to ensure complete isolation from production data."""

import tempfile
import os
import sys
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

# Add parent directory to path for standalone execution
if __name__ == "__main__":
    parent_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(parent_dir))

from utils.db_utils import AssignmentDB


class IsolatedTestEnvironment:
    """Isolated test environment that prevents production data contamination."""
    
    def __init__(self):
        self.temp_dir = None
        self.temp_db_path = None
        self.test_db = None
    
    def __enter__(self):
        """Enter test environment - create isolated resources."""
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp(prefix='schwab_test_')
        
        # Create temporary database
        self.temp_db_path = os.path.join(self.temp_dir, 'test_assignments.db')
        self.test_db = AssignmentDB(self.temp_db_path)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit test environment - cleanup all resources."""
        if self.temp_db_path and Path(self.temp_db_path).exists():
            Path(self.temp_db_path).unlink()
        
        if self.temp_dir and Path(self.temp_dir).exists():
            import shutil
            shutil.rmtree(self.temp_dir)
    
    def get_test_db(self) -> AssignmentDB:
        """Get isolated test database."""
        if not self.test_db:
            raise RuntimeError("Test environment not properly initialized")
        return self.test_db


@contextmanager
def isolated_test_environment() -> Generator[IsolatedTestEnvironment, None, None]:
    """Context manager for completely isolated test environment."""
    with IsolatedTestEnvironment() as test_env:
        yield test_env


def ensure_not_production_db(db_path: str) -> None:
    """Safety check to ensure we're not using production database."""
    production_paths = [
        'data/assignments.db',
        './data/assignments.db',
        '/data/assignments.db'
    ]
    
    # Normalize path for comparison
    normalized_path = os.path.normpath(db_path)
    
    for prod_path in production_paths:
        if normalized_path.endswith(os.path.normpath(prod_path)):
            raise RuntimeError(
                f"SAFETY ERROR: Attempted to use production database '{db_path}' in tests! "
                f"Use isolated_test_environment() or temp_db fixture instead."
            )


def create_test_assignment_data():
    """Create sample assignment data for testing."""
    return [
        {
            'transactionId': 'TEST_001',
            'transactionType': 'ASSIGNMENT',
            'instrument': {'symbol': 'AAPL  241220P00150000'},
            'quantity': -100,
            'price': 150.00,
            'transactionDate': '2024-12-20T21:00:00Z'
        },
        {
            'transactionId': 'TEST_002', 
            'transactionType': 'EXERCISE_ASSIGNMENT',
            'instrument': {'symbol': 'MSFT  241220C00400000'},
            'quantity': -200,
            'price': 400.00,
            'transactionDate': '2024-12-20T21:00:00Z'
        }
    ]


def create_test_assignments_with_mixed_types():
    """Create test data with both PUT and CALL assignments."""
    return [
        # PUT assignment - we get assigned shares
        {
            'transactionId': 'TEST_PUT_001',
            'transactionType': 'ASSIGNMENT',
            'instrument': {'symbol': 'XYZ   241220P00050000'},
            'quantity': -200,  # 2 contracts = 200 shares
            'price': 50.00,
            'transactionDate': '2024-01-15T21:00:00Z'
        },
        # CALL assignment - shares get called away
        {
            'transactionId': 'TEST_CALL_001',
            'transactionType': 'EXERCISE_ASSIGNMENT',
            'instrument': {'symbol': 'XYZ   241220C00055000'},
            'quantity': -100,  # 1 contract = 100 shares called away
            'price': 55.00,
            'transactionDate': '2024-02-15T21:00:00Z'
        }
    ]


def verify_test_isolation():
    """Verify that we're in a proper test environment."""
    # Check that we're not accidentally using production files
    production_files = [
        'data/assignments.db',
        'data/account/account_snapshot.json',
        'data/auth/schwab_tokens.json'
    ]
    
    warnings = []
    for file_path in production_files:
        if Path(file_path).exists():
            warnings.append(f"Production file exists: {file_path}")
    
    if warnings:
        print("⚠️  WARNING: Production files detected during testing:")
        for warning in warnings:
            print(f"   {warning}")
        print("   Make sure tests use isolated environments!")
    else:
        print("✅ Test isolation verified - no production files in danger")


if __name__ == "__main__":
    # Quick verification when run directly
    verify_test_isolation()
    
    # Demo isolated environment
    print("\n🧪 Testing isolated environment...")
    with isolated_test_environment() as test_env:
        db = test_env.get_test_db()
        print(f"   Created isolated DB at: {db.db_path}")
        
        # Test some operations
        from utils.assignments import normalize_assignment_event
        test_data = create_test_assignment_data()[0]
        normalized = normalize_assignment_event(test_data, "test_account")
        
        if normalized:
            db.upsert_assignment(normalized)
            print(f"   Successfully tested assignment insertion")
        
        # Verify it's isolated
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM assignments")
            count = cursor.fetchone()['count']
            print(f"   Test DB has {count} assignment(s)")
    
    print("   Test environment cleaned up automatically")
    print("✅ Isolated testing infrastructure working correctly!")