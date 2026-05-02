#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import sys
import os
import time
import threading

# ════════════════════════════════════════════════════════════
# Configuration constants
# ════════════════════════════════════════════════════════════
ETHERNET_FRAME_MIN = 64  # Minimum Ethernet frame size (bytes)
ETHERNET_FRAME_MAX = 1518  # Maximum Ethernet frame size (bytes)
ETHERNET_HEADER_SIZE = 14

# MAC aging configuration
MAC_AGING_TIMEOUT = 1800  # 30 minutes: remove MAC entries after this many seconds
MAC_AGING_CHECK_INTERVAL = 60  # Check every 60 seconds for stale entries

# ════════════════════════════════════════════════════════════
# Helper functions for validation
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
    
    # Check frame size bounds
    frame_size = len(data)
    if frame_size < ETHERNET_HEADER_SIZE:
        return False, None, None, f"Frame too small ({frame_size} < {ETHERNET_HEADER_SIZE})"
    
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

def age_mac_entries(mac_table, current_time, timeout=MAC_AGING_TIMEOUT):
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
# Main VSwitch
# ════════════════════════════════════════════════════════════

# parse parameters
server_port = None
if len(sys.argv) < 2 or len(sys.argv) > 3:
    print("Usage: python3 vswitch.py {VSWITCH_PORT} [BIND_IP]")
    sys.exit(1)
else:
    try:
        server_port = int(sys.argv[1])
        if server_port < 1 or server_port > 65535:
            raise ValueError("Port out of range")
        server_ip = sys.argv[2] if len(sys.argv) == 3 else "0.0.0.0"
    except ValueError as e:
        print(f"Error: Invalid port ({e})")
        sys.exit(1)

server_addr = (server_ip, server_port)

# 0. create UDP socket, bind to service port
try:
    vserver_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    vserver_sock.bind(server_addr)
    print(f"[VSwitch] Started at {server_addr[0]}:{server_addr[1]}")
except Exception as e:
    print(f"[VSwitch] ERROR: Failed to bind socket: {e}")
    sys.exit(1)

mac_table = {}
stats = {
    "frames_received": 0,
    "frames_forwarded": 0,
    "frames_dropped": 0,
    "frames_invalid": 0
}

# Track time for MAC aging
last_aging_check = time.time()

while True:
    try:
        current_time = time.time()
        
        # Periodically check for and remove stale MAC entries
        if current_time - last_aging_check > MAC_AGING_CHECK_INTERVAL:
            removed, remaining = age_mac_entries(mac_table, current_time)
            if removed > 0:
                print(f"    MAC Table: {remaining} entries")
            last_aging_check = current_time
        
        # 1. read ethernet frame from VPort
        data, vport_addr = vserver_sock.recvfrom(ETHERNET_FRAME_MAX + 100)  # Extra buffer
        stats["frames_received"] += 1
        current_time = time.time()

        # 2. validate ethernet frame
        is_valid, eth_src, eth_dst, error_reason = validate_frame(data, vport_addr)
        
        if not is_valid:
            stats["frames_invalid"] += 1
            print(
                f"[VSwitch] INVALID frame from {vport_addr}: {error_reason} (size: {len(data)})"
            )
            continue

        # 3. log frame details
        print(
            f"[VSwitch] vport_addr<{vport_addr}> "
            f"src<{eth_src}> dst<{eth_dst}> datasz<{len(data)}>"
        )

        # 4. insert/update mac table with timestamp
        if eth_src not in mac_table or mac_table[eth_src][0] != vport_addr:
            mac_table[eth_src] = (vport_addr, current_time)
            print(f"    Learned: {eth_src} → {vport_addr}")

        # 5. forward ethernet frame
        #    if dest in mac table, forward ethernet frame to it
        if eth_dst in mac_table:
            try:
                vport_dest, _ = mac_table[eth_dst]
                vserver_sock.sendto(data, vport_dest)
                stats["frames_forwarded"] += 1
                print(f"    Forwarded to: {eth_dst}")
            except Exception as e:
                stats["frames_dropped"] += 1
                print(f"    ERROR forwarding to {eth_dst}: {e}")

        #    broadcast ethernet frame to every known VPort except source VPort
        elif eth_dst == "ff:ff:ff:ff:ff:ff":
            try:
                brd_dst_macs = list(mac_table.keys())
                if eth_src in brd_dst_macs:
                    brd_dst_macs.remove(eth_src)
                brd_dst_vports = {mac_table[mac][0] for mac in brd_dst_macs}
                
                if brd_dst_vports:
                    print(f"    Broadcasted to {len(brd_dst_vports)} peer(s)")
                    for brd_dst in brd_dst_vports:
                        vserver_sock.sendto(data, brd_dst)
                    stats["frames_forwarded"] += len(brd_dst_vports)
                else:
                    print(f"    Broadcast dropped (no other peers)")
            except Exception as e:
                print(f"    ERROR broadcasting: {e}")
                stats["frames_dropped"] += 1
        else:
            stats["frames_dropped"] += 1
            print(f"    Discarded (unknown destination MAC)")

    except socket.error as e:
        print(f"[VSwitch] Socket error: {e}")
        continue
    except KeyboardInterrupt:
        print(f"\n[VSwitch] Shutting down...")
        print(f"Stats: {stats}")
        break
    except Exception as e:
        print(f"[VSwitch] Unexpected error: {e}")
        continue
