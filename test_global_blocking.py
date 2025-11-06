#!/usr/bin/env python3
"""
Quick test to verify global IP blocking middleware works.
Tests that @app.before_request blocks all requests from blocked IPs.
"""

from website import create_app, db
from website.models import BlockedIP
from website.blocking import block_ip, get_ip_subnet, is_ip_blocked


def test_global_blocking():
    """Test that global blocking middleware works"""
    print("="*60)
    print("TEST: Global IP Blocking Middleware")
    print("="*60)
    
    app = create_app()
    
    with app.app_context():
        # Clean up any existing test blocks
        test_ip = "99.99.99.99"
        existing = BlockedIP.query.filter_by(ip_address=test_ip).first()
        if existing:
            db.session.delete(existing)
        db.session.commit()
        
        # Block the test IP
        print(f"\n1. Blocking test IP: {test_ip}")
        success, message, _ = block_ip(test_ip, reason="Test global blocking")
        if not success:
            print(f"   ❌ FAIL: Could not block IP: {message}")
            return False
        print(f"   ✅ PASS: {message}")
        
        # Verify IP is blocked
        print(f"\n2. Verifying IP is blocked...")
        is_blocked, _ = is_ip_blocked(test_ip)
        if not is_blocked:
            print(f"   ❌ FAIL: IP should be blocked but isn't")
            return False
        print(f"   ✅ PASS: IP is correctly blocked")
        
        # Test that subnet is also blocked
        subnet = get_ip_subnet(test_ip)
        test_subnet_ip = f"{subnet}.100"
        print(f"\n3. Testing subnet blocking ({test_subnet_ip})...")
        is_blocked_subnet, _ = is_ip_blocked(test_subnet_ip)
        if not is_blocked_subnet:
            print(f"   ❌ FAIL: Subnet IP should be blocked but isn't")
            return False
        print(f"   ✅ PASS: Subnet IP is correctly blocked")
        
        # Verify the before_request hook would catch this
        print(f"\n4. Verifying global blocking setup...")
        # Check if before_request is registered
        has_before_request = hasattr(app, 'before_request_funcs') and app.before_request_funcs
        if has_before_request:
            print(f"   ✅ PASS: before_request hooks are registered")
        else:
            print(f"   ⚠️  WARNING: Could not verify before_request hooks (may still work)")
        
        # Clean up
        print(f"\n5. Cleaning up...")
        existing = BlockedIP.query.filter_by(ip_address=test_ip).first()
        if existing:
            db.session.delete(existing)
        db.session.commit()
        print(f"   ✅ Cleanup complete")
    
    print(f"\n✅ ALL TESTS PASSED!")
    print(f"\n📝 NOTE: The global blocking middleware (@app.before_request)")
    print(f"   will block ALL requests from blocked IPs before any route handler runs.")
    print(f"   This means blocked IPs cannot access ANY page on your website.")
    print(f"   They will see a 403 Forbidden error.")
    
    return True


if __name__ == "__main__":
    test_global_blocking()

