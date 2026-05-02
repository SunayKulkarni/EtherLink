#!/usr/bin/env python3
"""
Test script for Ethernet frame validation in vswitch.py
"""

import sys
import os
sys.path.insert(0, '/home/sunaykulkarni/Projects/networking/EtherLink')

# ════════════════════════════════════════════════════════════
# Import validation functions from vswitch
# ════════════════════════════════════════════════════════════

def is_valid_mac(mac_str):
    """Validate MAC address format (xx:xx:xx:xx:xx:xx)"""
    try:
        parts = mac_str.split(":")
        if len(parts) != 6:
            return False
        for part in parts:
            if len(part) != 2 or int(part, 16) < 0 or int(part, 16) > 255:
                return False
        return True
    except:
        return False

def validate_frame(data, vport_addr):
    """
    Validate Ethernet frame: check size and header validity
    Returns: (is_valid, eth_src, eth_dst, reason)
    """
    ETHERNET_FRAME_MIN = 64
    ETHERNET_FRAME_MAX = 1518
    ETHERNET_HEADER_SIZE = 14
    
    # Check frame size bounds
    frame_size = len(data)
    if frame_size < ETHERNET_HEADER_SIZE:
        return False, None, None, f"Frame too small ({frame_size} < {ETHERNET_HEADER_SIZE})"
    
    if frame_size < ETHERNET_FRAME_MIN:
        return False, None, None, f"Frame below minimum ({frame_size} < {ETHERNET_FRAME_MIN})"
    
    if frame_size > ETHERNET_FRAME_MAX:
        return False, None, None, f"Frame exceeds maximum ({frame_size} > {ETHERNET_FRAME_MAX})"
    
    # Parse and validate Ethernet header
    try:
        eth_header = data[:ETHERNET_HEADER_SIZE]
        
        # Extract MACs
        eth_dst = ":".join("{:02x}".format(x) for x in eth_header[0:6])
        eth_src = ":".join("{:02x}".format(x) for x in eth_header[6:12])
        
        # Validate MAC addresses
        if not is_valid_mac(eth_src):
            return False, None, None, f"Invalid source MAC: {eth_src}"
        
        if not is_valid_mac(eth_dst):
            return False, None, None, f"Invalid destination MAC: {eth_dst}"
        
        return True, eth_src, eth_dst, None
        
    except Exception as e:
        return False, None, None, f"Header parsing error: {str(e)}"

# ════════════════════════════════════════════════════════════
# Test Cases
# ════════════════════════════════════════════════════════════

def create_valid_frame():
    """Create a valid 64-byte Ethernet frame"""
    # Destination MAC: 00:11:22:33:44:55
    # Source MAC: aa:bb:cc:dd:ee:ff
    # Type: 0x0800 (IPv4)
    # Payload: padding to reach 64 bytes minimum
    frame = bytes([
        0x00, 0x11, 0x22, 0x33, 0x44, 0x55,  # Dest MAC (6 bytes)
        0xaa, 0xbb, 0xcc, 0xdd, 0xee, 0xff,  # Src MAC (6 bytes)
        0x08, 0x00,                          # Type (2 bytes)
    ])
    # Pad to 64 bytes minimum
    frame += b'\x00' * (64 - len(frame))
    return frame

def create_broadcast_frame():
    """Create a broadcast frame (ff:ff:ff:ff:ff:ff)"""
    frame = bytes([
        0xff, 0xff, 0xff, 0xff, 0xff, 0xff,  # Broadcast MAC
        0xaa, 0xbb, 0xcc, 0xdd, 0xee, 0xff,  # Src MAC
        0x08, 0x00,                           # Type
    ])
    frame += b'\x00' * (64 - len(frame))
    return frame

test_cases = [
    # (description, frame, should_pass)
    ("Valid 64-byte frame", create_valid_frame(), True),
    ("Valid broadcast frame", create_broadcast_frame(), True),
    ("Frame too small (13 bytes)", b'\x00' * 13, False),
    ("Frame under minimum (50 bytes)", b'\x00' * 50, False),
    ("Frame over maximum (1519 bytes)", b'\x00' * 1519, False),
    ("Frame at max (1518 bytes)", b'\x00' * 1518, True),
    ("Frame at min (64 bytes)", create_valid_frame(), True),
]

# ════════════════════════════════════════════════════════════
# Run Tests
# ════════════════════════════════════════════════════════════

print("════════════════════════════════════════════════════════════")
print("✓ Input Validation Test Suite")
print("════════════════════════════════════════════════════════════")
print()

passed = 0
failed = 0

for description, frame, should_pass in test_cases:
    is_valid, eth_src, eth_dst, error = validate_frame(frame, ("127.0.0.1", 9999))
    
    if is_valid == should_pass:
        status = "✓ PASS"
        passed += 1
    else:
        status = "✗ FAIL"
        failed += 1
    
    print(f"{status}: {description}")
    print(f"  Size: {len(frame)} bytes")
    
    if is_valid:
        print(f"  Source MAC: {eth_src}")
        print(f"  Destination MAC: {eth_dst}")
    else:
        print(f"  Error: {error}")
    print()

print("════════════════════════════════════════════════════════════")
print(f"Results: {passed} passed, {failed} failed")
print("════════════════════════════════════════════════════════════")

if failed > 0:
    sys.exit(1)
