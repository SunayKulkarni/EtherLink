#!/usr/bin/env python3
"""
Test script for MAC entry aging in vswitch.py
"""

import time
import sys

# ════════════════════════════════════════════════════════════
# Simulate MAC aging
# ════════════════════════════════════════════════════════════

def age_mac_entries(mac_table, current_time, timeout=1800):
    """
    Remove MAC entries that haven't been seen for 'timeout' seconds
    Returns: (removed_count, remaining_count)
    """
    expired_macs = []
    
    for mac_addr, (vport_addr, timestamp) in mac_table.items():
        if current_time - timestamp > timeout:
            expired_macs.append(mac_addr)
    
    # Remove expired entries
    for mac_addr in expired_macs:
        vport_addr, timestamp = mac_table.pop(mac_addr)
        age_seconds = current_time - timestamp
        print(f"[VSwitch] AGED: {mac_addr} → {vport_addr} (age: {age_seconds:.0f}s)")
    
    return len(expired_macs), len(mac_table)

# ════════════════════════════════════════════════════════════
# Test Cases
# ════════════════════════════════════════════════════════════

print("════════════════════════════════════════════════════════════")
print("🔄 MAC Entry Aging Test")
print("════════════════════════════════════════════════════════════")
print()

# Create a mac_table with some entries
# Format: mac -> (vport_address_tuple, timestamp)
base_time = 10000.0
mac_table = {
    "aa:bb:cc:dd:ee:01": (("192.168.1.1", 5000), base_time),                    # Recent (age 0s)
    "aa:bb:cc:dd:ee:02": (("192.168.1.2", 5000), base_time - 60),               # 1 minute ago
    "aa:bb:cc:dd:ee:03": (("192.168.1.3", 5000), base_time - 1799),            # 29m 59s ago (just under timeout)
    "aa:bb:cc:dd:ee:04": (("192.168.1.4", 5000), base_time - 1801),            # 30m 1s ago (just over timeout, will be removed)
    "aa:bb:cc:dd:ee:05": (("192.168.1.5", 5000), base_time - 3600),            # 1 hour ago (definitely expired)
}

print("Initial MAC Table:")
for mac, (addr, ts) in mac_table.items():
    age = base_time - ts
    print(f"  {mac} → {addr[0]}:{addr[1]} (age: {age:.0f}s)")
print()

# Test 1: No aging yet (timeout = 1800s)
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("Test 1: Check at current_time (some old entries will be aged)")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
removed, remaining = age_mac_entries(mac_table, base_time, timeout=1800)
print(f"Result: {removed} removed, {remaining} remaining")
assert removed == 2, f"Should remove 2 entries (04 and 05, both > 1800s old) (got {removed})"
assert remaining == 3, f"Should have 3 remaining (01, 02, 03) (got {remaining})"
print("✓ PASS: 2 old entries aged out")
print()

# Reset for next test - entries created at different times
mac_table = {
    "aa:bb:cc:dd:ee:01": (("192.168.1.1", 5000), base_time - 100),       # 100s ago (young)
    "aa:bb:cc:dd:ee:02": (("192.168.1.2", 5000), base_time - 500),       # 500s ago (still young)
    "aa:bb:cc:dd:ee:03": (("192.168.1.3", 5000), base_time - 1500),      # 1500s ago (approaching timeout)
    "aa:bb:cc:dd:ee:04": (("192.168.1.4", 5000), base_time - 1801),      # 1801s ago (over timeout)
    "aa:bb:cc:dd:ee:05": (("192.168.1.5", 5000), base_time - 3600),      # 3600s ago (way over timeout)
}

# Test 2: Some entries aged at base_time (no new time passed)
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("Test 2: Check which entries exceed 1800s timeout at base_time")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
removed, remaining = age_mac_entries(mac_table, base_time, timeout=1800)
print(f"Result: {removed} removed, {remaining} remaining")
assert removed == 2, f"Should remove 2 entries (04 and 05, both > 1800s) (got {removed})"
assert remaining == 3, f"Should have 3 remaining (01, 02, 03) (got {remaining})"
print("✓ PASS: 2 entries aged out")
print()

# Test 3: All entries aged
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("Test 3: After 2000 seconds have passed (all entries old)")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
removed, remaining = age_mac_entries(mac_table, base_time + 2000, timeout=1800)
print(f"Result: {removed} removed, {remaining} remaining")
assert remaining == 0, f"MAC table should be empty (got {remaining})"
print("✓ PASS: All entries aged out")
print()

# Test 4: Empty table
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("Test 4: Handle empty MAC table")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
mac_table = {}
removed, remaining = age_mac_entries(mac_table, base_time, timeout=1800)
print(f"Result: {removed} removed, {remaining} remaining")
assert remaining == 0, "Empty table should have 0 entries"
print("✓ PASS: Empty table handled")
print()

print("════════════════════════════════════════════════════════════")
print("✅ MAC Aging Test Complete!")
print("════════════════════════════════════════════════════════════")
print()
print("How MAC aging works:")
print("  - Each MAC entry stores: (vport_address, timestamp)")
print("  - Every 60 seconds, vswitch checks for expired entries")
print("  - Entries older than 30 minutes (1800s) are removed")
print("  - This prevents stale mappings from persisting")
print()
print("Benefits:")
print("  - Network topology changes handled gracefully")
print("  - Clients that disconnect are forgotten")
print("  - Reduces memory usage over time")
print()
