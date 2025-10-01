#!/usr/bin/env python3
"""Safe testing and demonstration script that never touches production data."""

import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from tests.test_utils import isolated_test_environment, create_test_assignments_with_mixed_types
from utils.assignments import normalize_assignment_event, fetch_and_record_assignments
from api.sim_client import SimBrokerClient


def demo_call_put_accounting():
    """Demonstrate CALL/PUT assignment accounting in isolated environment."""
    print("🧪 DEMONSTRATING CALL/PUT ASSIGNMENT ACCOUNTING")
    print("=" * 60)
    print("✅ Using completely isolated test environment - NO production data affected!")
    print()
    
    with isolated_test_environment() as test_env:
        db = test_env.get_test_db()
        
        # Create test assignments: PUT then CALL
        test_assignments = create_test_assignments_with_mixed_types()
        
        print("📋 Processing test assignments:")
        for i, assignment in enumerate(test_assignments, 1):
            normalized = normalize_assignment_event(assignment, "test_account")
            if normalized:
                db.upsert_assignment(normalized)
                
                # Record basis tracking
                if normalized['price_per_share']:
                    db.record_assignment_basis(
                        normalized['ticker'],
                        normalized['shares'], 
                        normalized['price_per_share'],
                        normalized['assigned_at'],
                        normalized['option_type']
                    )
                
                print(f"  {i}. {normalized['option_type']} - {normalized['shares']} shares of {normalized['ticker']} @ ${normalized['price_per_share']}")
        
        print()
        print("📊 FINAL POSITION AFTER BOTH ASSIGNMENTS:")
        
        # Check final position
        with db.get_connection() as conn:
            cursor = conn.execute('SELECT * FROM assigned_basis WHERE ticker = "XYZ"')
            result = cursor.fetchone()
            
            if result:
                shares = result['total_shares']
                cost = result['total_cost']
                basis = result['avg_basis']
                count = result['assignment_count']
                
                print(f"  XYZ: {shares} shares remaining")
                print(f"  Total cost: ${cost:.2f}")
                print(f"  Average basis: ${basis:.2f}")
                print(f"  Assignment count: {count}")
                
                print()
                print("🧮 VERIFICATION:")
                print("  Initial: PUT 200 shares @ $50.00 = $10,000 cost")
                print("  Called:  CALL 100 shares @ $55.00 = -$5,500 cost (we received money)")
                print("  Final:   100 shares @ $45.00 average = $4,500 remaining cost")
                print("  Math:    $10,000 - $5,500 = $4,500 ✓")
                print("           $4,500 ÷ 100 shares = $45.00 average ✓")
                
                expected_shares = 100
                expected_cost = 4500.0
                expected_basis = 45.0
                
                if (shares == expected_shares and 
                    abs(cost - expected_cost) < 0.01 and 
                    abs(basis - expected_basis) < 0.01):
                    print("✅ All calculations correct!")
                else:
                    print("❌ Calculation error detected")
            else:
                print("❌ No position found")
    
    print("\n🔒 Test environment automatically cleaned up - production data untouched!")


def demo_assignment_detection():
    """Demonstrate assignment detection in isolated environment."""
    print("\n🔍 DEMONSTRATING ASSIGNMENT DETECTION")
    print("=" * 50)
    
    with isolated_test_environment() as test_env:
        db = test_env.get_test_db()
        
        # Create mock client with test data
        from tests.test_utils import create_test_assignment_data
        test_data = create_test_assignment_data()
        mock_client = SimBrokerClient()
        
        # Simulate fetching assignments (but with test data)
        print("📥 Simulating assignment fetch from broker...")
        
        for assignment in test_data:
            normalized = normalize_assignment_event(assignment, "test_account")
            if normalized:
                was_inserted = db.upsert_assignment(normalized)
                print(f"  ✓ Detected: {normalized['ticker']} {normalized['option_type']} assignment")
                
                if was_inserted and normalized['price_per_share']:
                    db.record_assignment_basis(
                        normalized['ticker'],
                        normalized['shares'],
                        normalized['price_per_share'],
                        normalized['assigned_at'],
                        normalized['option_type']
                    )
        
        # Show summary
        with db.get_connection() as conn:
            cursor = conn.execute('SELECT COUNT(*) as count FROM assignments')
            total = cursor.fetchone()['count']
            
            cursor = conn.execute('SELECT ticker, total_shares, avg_basis FROM assigned_basis')
            positions = cursor.fetchall()
            
            print(f"\n📊 SUMMARY: {total} assignments processed")
            for pos in positions:
                print(f"  {pos['ticker']}: {pos['total_shares']} shares @ ${pos['avg_basis']:.2f}")
    
    print("\n🔒 Test complete - production data safe!")


if __name__ == "__main__":
    print("🛡️  SAFE TESTING MODE - Production Data Protected")
    print("=" * 70)
    
    # Run demonstrations
    demo_call_put_accounting()
    demo_assignment_detection()
    
    print("\n" + "=" * 70)
    print("✅ All demonstrations completed safely!")
    print("🔒 Your production data in data/assignments.db was never touched!")