"""Tests for option assignment tracking system."""

import pytest
import tempfile
import json
from datetime import datetime, timezone
from pathlib import Path

from utils.db_utils import AssignmentDB, generate_assignment_id
from utils.assignments import (
    looks_like_assignment, extract_option_details, normalize_assignment_event,
    fetch_and_record_assignments, get_assignment_impact_on_positions
)


class MockBrokerClient:
    """Mock broker client for testing."""
    
    def __init__(self, transactions=None):
        self.transactions = transactions or []
        self.account_hash = "test_account_123"
    
    def account_transactions(self, from_date=None, to_date=None):
        return self.transactions


@pytest.fixture
def temp_db():
    """Temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    db = AssignmentDB(db_path)
    yield db
    
    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def sample_assignment_transaction():
    """Sample assignment transaction from broker."""
    return {
        'transactionId': 'TXN_12345',
        'transactionType': 'ASSIGNMENT',
        'instrument': {
            'symbol': 'AAPL  231215C00150000',
            'assetType': 'OPTION'
        },
        'quantity': -100,  # Assigned 100 shares (1 contract)
        'price': 150.50,
        'netAmount': -15050.00,
        'transactionDate': '2023-12-15T20:30:00Z',
        'orderId': 'ORDER_67890',
        'description': 'AAPL Call Option Assignment'
    }


@pytest.fixture
def duplicate_assignment_transaction():
    """Duplicate of sample assignment for testing idempotency."""
    return {
        'transactionId': 'TXN_12345',  # Same ID as sample
        'transactionType': 'ASSIGNMENT',
        'instrument': {
            'symbol': 'AAPL  231215C00150000',
            'assetType': 'OPTION'
        },
        'quantity': -100,
        'price': 150.50,
        'netAmount': -15050.00,
        'transactionDate': '2023-12-15T20:30:00Z',
        'orderId': 'ORDER_67890',
        'description': 'AAPL Call Option Assignment'
    }


@pytest.fixture
def partial_assignment_transactions():
    """Two partial assignments for the same contract."""
    return [
        {
            'transactionId': 'TXN_PARTIAL_1',
            'transactionType': 'ASSIGNMENT',
            'instrument': {'symbol': 'MSFT  240119P00300000'},
            'quantity': -1,  # 1 contract = 100 shares
            'price': 300.00,
            'transactionDate': '2024-01-19T21:00:00Z'
        },
        {
            'transactionId': 'TXN_PARTIAL_2', 
            'transactionType': 'ASSIGNMENT',
            'instrument': {'symbol': 'MSFT  240119P00300000'},
            'quantity': -1,  # Another 1 contract = 100 shares  
            'price': 300.00,
            'transactionDate': '2024-01-19T21:01:00Z'
        }
    ]


@pytest.fixture
def missing_price_transaction():
    """Assignment transaction missing price data."""
    return {
        'transactionId': 'TXN_NO_PRICE',
        'transactionType': 'EXERCISE_ASSIGNMENT',
        'instrument': {'symbol': 'GOOGL 241220C02500000'},
        'quantity': -200,
        'transactionDate': '2024-12-20T20:00:00Z',
        'description': 'GOOGL Call Assignment - price TBD'
    }


class TestAssignmentDetection:
    """Test assignment detection logic."""
    
    def test_looks_like_assignment_direct_match(self):
        """Test direct transaction type matches."""
        assert looks_like_assignment('ASSIGNMENT', {})
        assert looks_like_assignment('EXERCISE', {})
        assert looks_like_assignment('EXERCISE_ASSIGNMENT', {})
        assert looks_like_assignment('AUTO_EXERCISE', {})
        
    def test_looks_like_assignment_case_insensitive(self):
        """Test case insensitive matching."""
        assert looks_like_assignment('assignment', {})
        assert looks_like_assignment('Assignment', {})
        assert looks_like_assignment('ASSIGNMENT', {})
        
    def test_looks_like_assignment_partial_match(self):
        """Test partial string matching."""
        assert looks_like_assignment('EARLY_EXERCISE_CALL', {})
        assert looks_like_assignment('OPTION_ASSIGNMENT_PUT', {})
        
    def test_looks_like_assignment_description_fallback(self):
        """Test detection via description field."""
        tx = {'description': 'AAPL Call Option was assigned to account'}
        assert looks_like_assignment('TRADE', tx)
        
        tx = {'description': 'Option exercised early'}
        assert looks_like_assignment('TRADE', tx)  # Need valid transaction type
        
    def test_looks_like_assignment_negative_cases(self):
        """Test cases that should not be detected as assignments."""
        assert not looks_like_assignment('BUY', {})
        assert not looks_like_assignment('SELL', {})
        assert not looks_like_assignment('DIVIDEND', {})
        assert not looks_like_assignment('', {})
        assert not looks_like_assignment(None, {})


class TestOptionDetailsExtraction:
    """Test option contract symbol parsing."""
    
    def test_extract_option_details_call(self):
        """Test parsing call option."""
        details = extract_option_details('AAPL  231215C00150000')
        assert details['ticker'] == 'AAPL'
        assert details['option_type'] == 'CALL'
        assert details['strike'] == 150.0
        assert details['expiry'].year == 2023
        assert details['expiry'].month == 12
        assert details['expiry'].day == 15
        
    def test_extract_option_details_put(self):
        """Test parsing put option."""
        details = extract_option_details('MSFT  240119P00300000')
        assert details['ticker'] == 'MSFT'
        assert details['option_type'] == 'PUT'
        assert details['strike'] == 300.0
        assert details['expiry'].year == 2024
        
    def test_extract_option_details_high_strike(self):
        """Test parsing high strike price."""
        details = extract_option_details('GOOGL 241220C02500000')
        assert details['ticker'] == 'GOOGL'
        assert details['strike'] == 2500.0
        
    def test_extract_option_details_fractional_strike(self):
        """Test parsing fractional strike price."""
        details = extract_option_details('SPY   240315C00412500')
        assert details['ticker'] == 'SPY'
        assert details['strike'] == 412.5
        
    def test_extract_option_details_invalid_format(self):
        """Test invalid option symbols."""
        assert extract_option_details('INVALID') is None
        assert extract_option_details('') is None
        assert extract_option_details(None) is None
        assert extract_option_details('AAPL231215C150') is None  # Too short


class TestAssignmentNormalization:
    """Test assignment event normalization."""
    
    def test_normalize_assignment_event_complete(self, sample_assignment_transaction):
        """Test normalizing complete assignment event."""
        normalized = normalize_assignment_event(sample_assignment_transaction, 'test_account')
        
        assert normalized['id'] == 'TXN_12345'
        assert normalized['account_hash'] == 'test_account'
        assert normalized['option_symbol'] == 'AAPL  231215C00150000'
        assert normalized['ticker'] == 'AAPL'
        assert normalized['contracts'] == 1
        assert normalized['shares'] == 100
        assert normalized['price_per_share'] == 150.50
        assert normalized['total_amount'] == 15050.0
        assert normalized['transaction_type'] == 'ASSIGNMENT'
        assert normalized['related_order_id'] == 'ORDER_67890'
        
    def test_normalize_assignment_event_missing_price(self, missing_price_transaction):
        """Test normalizing assignment without price."""
        normalized = normalize_assignment_event(missing_price_transaction, 'test_account')
        
        assert normalized['id'] == 'TXN_NO_PRICE'
        assert normalized['ticker'] == 'GOOGL'
        assert normalized['contracts'] == 2  # 200 shares = 2 contracts
        assert normalized['shares'] == 200
        assert normalized['price_per_share'] is None
        assert normalized['total_amount'] is None
        
    def test_normalize_assignment_event_generated_id(self):
        """Test ID generation when broker doesn't provide one."""
        tx = {
            'transactionType': 'ASSIGNMENT',
            'instrument': {'symbol': 'TSLA  240601C00200000'},
            'quantity': -100,
            'price': 200.0,
            'transactionDate': '2024-06-01T20:00:00Z'
        }
        
        normalized = normalize_assignment_event(tx, 'test_account')
        assert normalized['id'] is not None
        assert len(normalized['id']) == 16  # Generated hash length
        
    def test_normalize_assignment_event_invalid_symbol(self):
        """Test handling invalid option symbol."""
        tx = {
            'transactionType': 'ASSIGNMENT',
            'instrument': {'symbol': 'INVALID_SYMBOL'},
            'quantity': -100,
            'transactionDate': '2024-01-01T20:00:00Z'
        }
        
        normalized = normalize_assignment_event(tx, 'test_account')
        assert normalized is None


class TestAssignmentDatabase:
    """Test assignment database operations."""
    
    def test_upsert_assignment_new_record(self, temp_db, sample_assignment_transaction):
        """Test inserting new assignment record."""
        normalized = normalize_assignment_event(sample_assignment_transaction, 'test_account')
        
        was_inserted = temp_db.upsert_assignment(normalized)
        assert was_inserted is True
        
        # Verify record exists
        assignments = temp_db.get_assignments_for_ticker('AAPL')
        assert len(assignments) == 1
        assert assignments[0]['id'] == 'TXN_12345'
        
    def test_upsert_assignment_duplicate(self, temp_db, sample_assignment_transaction, 
                                        duplicate_assignment_transaction):
        """Test duplicate assignment handling."""
        # Insert first record
        normalized1 = normalize_assignment_event(sample_assignment_transaction, 'test_account')
        was_inserted1 = temp_db.upsert_assignment(normalized1)
        assert was_inserted1 is True
        
        # Try to insert duplicate
        normalized2 = normalize_assignment_event(duplicate_assignment_transaction, 'test_account')
        was_inserted2 = temp_db.upsert_assignment(normalized2)
        assert was_inserted2 is False
        
        # Should still only have one record
        assignments = temp_db.get_assignments_for_ticker('AAPL')
        assert len(assignments) == 1
        
    def test_record_assignment_basis_new_ticker(self, temp_db):
        """Test recording assignment basis for new ticker."""
        temp_db.record_assignment_basis('AAPL', 100, 150.0, '2023-12-15T20:30:00Z', 'PUT')
        
        shares = temp_db.get_assigned_shares('AAPL')
        basis = temp_db.get_assigned_basis('AAPL')
        
        assert shares == 100
        assert basis == 150.0
        
    def test_record_assignment_basis_existing_ticker(self, temp_db):
        """Test recording additional basis for existing ticker."""
        # First assignment
        temp_db.record_assignment_basis('AAPL', 100, 150.0, '2023-12-15T20:30:00Z', 'PUT')
        
        # Second assignment
        temp_db.record_assignment_basis('AAPL', 100, 160.0, '2023-12-16T20:30:00Z', 'PUT')
        
        shares = temp_db.get_assigned_shares('AAPL')
        basis = temp_db.get_assigned_basis('AAPL')
        
        assert shares == 200
        assert basis == 155.0  # Average of 150 and 160
        
    def test_assignment_summary(self, temp_db, sample_assignment_transaction):
        """Test assignment summary statistics."""
        normalized = normalize_assignment_event(sample_assignment_transaction, 'test_account')
        temp_db.upsert_assignment(normalized)
        temp_db.record_assignment_basis('AAPL', 100, 150.0, '2023-12-15T20:30:00Z', 'PUT')
        
        summary = temp_db.get_assignment_summary()
        
        assert summary['total_assignments'] == 1
        assert len(summary['assignments_by_ticker']) == 1
        assert summary['assignments_by_ticker'][0]['ticker'] == 'AAPL'
        assert summary['assignments_by_ticker'][0]['total_shares'] == 100


class TestAssignmentFetching:
    """Test fetching assignments from broker."""
    
    def test_fetch_and_record_assignments_single(self, temp_db, sample_assignment_transaction):
        """Test fetching and recording single assignment."""
        client = MockBrokerClient([sample_assignment_transaction])
        
        recorded = fetch_and_record_assignments(client, temp_db)
        
        assert len(recorded) == 1
        assert recorded[0]['ticker'] == 'AAPL'
        
        # Verify in database
        assignments = temp_db.get_assignments_for_ticker('AAPL')
        assert len(assignments) == 1
        
    def test_fetch_and_record_assignments_partial(self, temp_db, partial_assignment_transactions):
        """Test handling partial assignments."""
        client = MockBrokerClient(partial_assignment_transactions)
        
        recorded = fetch_and_record_assignments(client, temp_db)
        
        assert len(recorded) == 2  # Two separate assignment events
        
        # Check basis tracking
        shares = temp_db.get_assigned_shares('MSFT')
        assert shares == 200  # 1 contract + 1 contract = 200 shares
        
    def test_fetch_and_record_assignments_missing_price(self, temp_db, missing_price_transaction):
        """Test handling assignment with missing price."""
        client = MockBrokerClient([missing_price_transaction])
        
        recorded = fetch_and_record_assignments(client, temp_db)
        
        assert len(recorded) == 1
        assert recorded[0]['price_per_share'] is None
        
        # Should still record the assignment but not update basis
        assignments = temp_db.get_assignments_for_ticker('GOOGL')
        assert len(assignments) == 1
        
        # No basis should be recorded due to missing price
        shares = temp_db.get_assigned_shares('GOOGL')
        assert shares == 0  # Not updated due to missing price
        
    def test_fetch_and_record_assignments_idempotent(self, temp_db, sample_assignment_transaction):
        """Test that multiple fetches are idempotent."""
        client = MockBrokerClient([sample_assignment_transaction])
        
        # First fetch
        recorded1 = fetch_and_record_assignments(client, temp_db)
        assert len(recorded1) == 1
        
        # Second fetch (same data)
        recorded2 = fetch_and_record_assignments(client, temp_db)
        assert len(recorded2) == 0  # No new records
        
        # Database should still have only one record
        assignments = temp_db.get_assignments_for_ticker('AAPL')
        assert len(assignments) == 1


class TestGenerateAssignmentId:
    """Test assignment ID generation."""
    
    def test_generate_assignment_id_stable(self):
        """Test that ID generation is stable for same inputs."""
        id1 = generate_assignment_id('AAPL  231215C00150000', 1, '2023-12-15T20:30:00Z', 150.0, 'account1')
        id2 = generate_assignment_id('AAPL  231215C00150000', 1, '2023-12-15T20:30:00Z', 150.0, 'account1')
        
        assert id1 == id2
        assert len(id1) == 16
        
    def test_generate_assignment_id_different_inputs(self):
        """Test that different inputs generate different IDs."""
        id1 = generate_assignment_id('AAPL  231215C00150000', 1, '2023-12-15T20:30:00Z', 150.0, 'account1')
        id2 = generate_assignment_id('AAPL  231215C00150000', 1, '2023-12-15T20:30:00Z', 151.0, 'account1')  # Different price
        
        assert id1 != id2
        
    def test_generate_assignment_id_null_price(self):
        """Test ID generation with null price."""
        id1 = generate_assignment_id('AAPL  231215C00150000', 1, '2023-12-15T20:30:00Z', None, 'account1')
        id2 = generate_assignment_id('AAPL  231215C00150000', 1, '2023-12-15T20:30:00Z', None, 'account1')
        
        assert id1 == id2


class TestAssignmentImpact:
    """Test assignment impact analysis."""
    
    def test_get_assignment_impact_on_positions(self, temp_db, sample_assignment_transaction):
        """Test getting assignment impact for a ticker."""
        # Record an assignment
        normalized = normalize_assignment_event(sample_assignment_transaction, 'test_account')
        temp_db.upsert_assignment(normalized)
        temp_db.record_assignment_basis('AAPL', 100, 150.0, '2023-12-15T20:30:00Z', 'PUT')
        
        impact = get_assignment_impact_on_positions('AAPL', temp_db)
        
        assert impact['ticker'] == 'AAPL'
        assert impact['assigned_shares'] == 100
        assert impact['assigned_basis'] == 150.0
        assert impact['total_assigned_cost'] == 15000.0
        assert impact['assignment_count'] == 1
        assert len(impact['recent_assignments']) == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])