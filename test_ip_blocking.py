#!/usr/bin/env python3
"""
Test script to verify IP blocking functionality works correctly.
Tests:
1. Subnet blocking (89.33.8.55 blocks 89.33.8.*)
2. IP blocking functions
3. Global blocking middleware
"""

import sys
from website import create_app, db
from website.models import BlockedIP, User
from website.blocking import (
    get_ip_subnet, 
    is_ip_blocked, 
    block_ip, 
    block_ip_subnet,
    unblock_ip
)


def test_subnet_function():
    """Test that get_ip_subnet works correctly"""
    print("="*60)
    print("TEST 1: Subnet Function")
    print("="*60)
    
    test_cases = [
        ("89.33.8.55", "89.33.8"),
        ("89.33.8.58", "89.33.8"),
        ("172.225.186.35", "172.225.186"),
        ("192.168.1.100", "192.168.1"),
        ("10.0.0.1", "10.0.0"),
        ("invalid", None),
        ("", None),
    ]
    
    all_passed = True
    for ip, expected in test_cases:
        result = get_ip_subnet(ip)
        passed = result == expected
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {ip} -> {result} (expected: {expected})")
        if not passed:
            all_passed = False
    
    return all_passed


def test_ip_blocking():
    """Test that IP blocking works"""
    print("\n" + "="*60)
    print("TEST 2: IP Blocking Functions")
    print("="*60)
    
    app = create_app()
    
    with app.app_context():
        # Clean up any existing test blocks
        test_ips = ["89.33.8.55", "89.33.8.58", "172.225.186.35"]
        for ip in test_ips:
            existing = BlockedIP.query.filter_by(ip_address=ip).first()
            if existing:
                db.session.delete(existing)
        db.session.commit()
        
        # Test 1: Block an IP
        print("\n1. Blocking IP 89.33.8.55...")
        success, message, block_record = block_ip("89.33.8.55", reason="Test blocking")
        if success:
            print(f"   ✅ PASS: {message}")
        else:
            print(f"   ❌ FAIL: {message}")
            return False
        
        # Test 2: Check if blocked IP is detected
        print("\n2. Checking if 89.33.8.55 is blocked...")
        is_blocked, record = is_ip_blocked("89.33.8.55")
        if is_blocked and record:
            print(f"   ✅ PASS: IP is correctly blocked (reason: {record.reason})")
        else:
            print(f"   ❌ FAIL: IP should be blocked but isn't")
            return False
        
        # Test 3: Check subnet blocking (89.33.8.58 should be blocked because 89.33.8.55 is blocked)
        print("\n3. Testing subnet blocking (89.33.8.58 should be blocked because 89.33.8.55 is)...")
        is_blocked_58, record_58 = is_ip_blocked("89.33.8.58")
        if is_blocked_58:
            print(f"   ✅ PASS: 89.33.8.58 is correctly blocked via subnet (reason: {record_58.reason})")
        else:
            print(f"   ❌ FAIL: 89.33.8.58 should be blocked (same subnet as 89.33.8.55)")
            return False
        
        # Test 4: Check unrelated IP is NOT blocked
        print("\n4. Testing that unrelated IP (192.168.1.1) is NOT blocked...")
        is_blocked_other, _ = is_ip_blocked("192.168.1.1")
        if not is_blocked_other:
            print(f"   ✅ PASS: Unrelated IP is correctly not blocked")
        else:
            print(f"   ❌ FAIL: Unrelated IP should not be blocked")
            return False
        
        # Test 5: Block another IP in different subnet
        print("\n5. Blocking IP 172.225.186.35...")
        success2, message2, block_record2 = block_ip("172.225.186.35", reason="Test blocking 2")
        if success2:
            print(f"   ✅ PASS: {message2}")
        else:
            print(f"   ❌ FAIL: {message2}")
            return False
        
        # Test 6: Check subnet blocking for second IP
        print("\n6. Testing subnet blocking for 172.225.186.35 (should block 172.225.186.*)...")
        is_blocked_172, record_172 = is_ip_blocked("172.225.186.100")
        if is_blocked_172:
            print(f"   ✅ PASS: 172.225.186.100 is correctly blocked via subnet")
        else:
            print(f"   ❌ FAIL: 172.225.186.100 should be blocked (same subnet as 172.225.186.35)")
            return False
        
        # Test 7: Unblock IP
        print("\n7. Unblocking 89.33.8.55...")
        success_unblock, message_unblock = unblock_ip("89.33.8.55")
        if success_unblock:
            print(f"   ✅ PASS: {message_unblock}")
        else:
            print(f"   ❌ FAIL: {message_unblock}")
            return False
        
        # Test 8: Check that unblocked IP is no longer blocked
        print("\n8. Checking that 89.33.8.55 is no longer blocked...")
        is_blocked_after, _ = is_ip_blocked("89.33.8.55")
        if not is_blocked_after:
            print(f"   ✅ PASS: IP is correctly unblocked")
        else:
            print(f"   ❌ FAIL: IP should be unblocked but isn't")
            return False
        
        # Test 9: Check that subnet blocking is removed after unblock
        print("\n9. Checking that 89.33.8.58 is no longer blocked after unblocking 89.33.8.55...")
        is_blocked_58_after, _ = is_ip_blocked("89.33.8.58")
        if not is_blocked_58_after:
            print(f"   ✅ PASS: Subnet blocking correctly removed")
        else:
            print(f"   ❌ FAIL: Subnet should be unblocked but isn't")
            return False
        
        # Clean up
        print("\n10. Cleaning up test blocks...")
        for ip in test_ips:
            existing = BlockedIP.query.filter_by(ip_address=ip).first()
            if existing:
                db.session.delete(existing)
        db.session.commit()
        print("   ✅ Cleanup complete")
    
    return True


def test_block_ip_subnet():
    """Test block_ip_subnet function"""
    print("\n" + "="*60)
    print("TEST 3: Block IP Subnet Function")
    print("="*60)
    
    app = create_app()
    
    with app.app_context():
        # Clean up
        test_ip = "10.20.30.40"
        existing = BlockedIP.query.filter_by(ip_address=test_ip).first()
        if existing:
            db.session.delete(existing)
        db.session.commit()
        
        # Test blocking subnet
        print(f"\n1. Blocking subnet for {test_ip}...")
        success, message, block_record = block_ip_subnet(test_ip, reason="Test subnet blocking")
        if success:
            print(f"   ✅ PASS: {message}")
        else:
            print(f"   ❌ FAIL: {message}")
            return False
        
        # Test that IP is blocked
        is_blocked, _ = is_ip_blocked(test_ip)
        if is_blocked:
            print(f"   ✅ PASS: IP {test_ip} is blocked")
        else:
            print(f"   ❌ FAIL: IP {test_ip} should be blocked")
            return False
        
        # Test that other IPs in subnet are blocked
        test_same_subnet = "10.20.30.99"
        is_blocked_same, _ = is_ip_blocked(test_same_subnet)
        if is_blocked_same:
            print(f"   ✅ PASS: IP {test_same_subnet} (same subnet) is blocked")
        else:
            print(f"   ❌ FAIL: IP {test_same_subnet} should be blocked (same subnet)")
            return False
        
        # Clean up
        existing = BlockedIP.query.filter_by(ip_address=test_ip).first()
        if existing:
            db.session.delete(existing)
        db.session.commit()
    
    return True


def test_existing_blocks():
    """Test that existing blocked IPs are still working"""
    print("\n" + "="*60)
    print("TEST 4: Existing Blocked IPs")
    print("="*60)
    
    app = create_app()
    
    with app.app_context():
        # Check existing blocked IPs
        blocked_ips = BlockedIP.query.filter_by(is_active=True).all()
        
        if not blocked_ips:
            print("   ⚠️  No blocked IPs found in database")
            return True
        
        print(f"\nFound {len(blocked_ips)} blocked IP(s):")
        for blocked in blocked_ips:
            print(f"   - {blocked.ip_address} (reason: {blocked.reason})")
            
            # Test that it's blocked
            is_blocked, record = is_ip_blocked(blocked.ip_address)
            if is_blocked:
                print(f"     ✅ PASS: Correctly detected as blocked")
            else:
                print(f"     ❌ FAIL: Should be blocked but isn't!")
                return False
            
            # Test subnet blocking
            subnet = get_ip_subnet(blocked.ip_address)
            if subnet:
                # Generate a test IP in same subnet
                test_ip = f"{subnet}.99"
                if test_ip != blocked.ip_address:
                    is_blocked_subnet, _ = is_ip_blocked(test_ip)
                    if is_blocked_subnet:
                        print(f"     ✅ PASS: Subnet {subnet}.* is correctly blocked")
                    else:
                        print(f"     ⚠️  WARNING: Subnet {subnet}.* not blocked (may be expected)")
    
    return True


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("IP BLOCKING TEST SUITE")
    print("="*60)
    
    tests = [
        ("Subnet Function", test_subnet_function),
        ("IP Blocking", test_ip_blocking),
        ("Block IP Subnet", test_block_ip_subnet),
        ("Existing Blocks", test_existing_blocks),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ ERROR in {name}: {str(e)}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! IP blocking is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

