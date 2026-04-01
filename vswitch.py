#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import sys
import os

# ════════════════════════════════════════════════════════════
# Input validation constants
# ════════════════════════════════════════════════════════════
ETHERNET_FRAME_MIN = 64  # Minimum Ethernet frame size (bytes)
ETHERNET_FRAME_MAX = 1518  # Maximum Ethernet frame size (bytes)
ETHERNET_HEADER_SIZE = 14

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
# Main VSwitch
# ════════════════════════════════════════════════════════════

# parse parameters
server_port = None
if len(sys.argv) != 2:
    print("Usage: python3 vswitch.py {VSWITCH_PORT}")
    sys.exit(1)
else:
    try:
        server_port = int(sys.argv[1])
        if server_port < 1 or server_port > 65535:
            raise ValueError("Port out of range")
    except ValueError as e:
        print(f"Error: Invalid port ({e})")
        sys.exit(1)

server_addr = ("0.0.0.0", server_port)

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

while True:
    try:
        # 1. read ethernet frame from VPort
        data, vport_addr = vserver_sock.recvfrom(ETHERNET_FRAME_MAX + 100)  # Extra buffer
        stats["frames_received"] += 1

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

        # 4. insert/update mac table
        if eth_src not in mac_table or mac_table[eth_src] != vport_addr:
            mac_table[eth_src] = vport_addr
            print(f"    Learned: {eth_src} → {vport_addr}")

        # 5. forward ethernet frame
        #    if dest in mac table, forward ethernet frame to it
        if eth_dst in mac_table:
            try:
                vserver_sock.sendto(data, mac_table[eth_dst])
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
                brd_dst_vports = {mac_table[mac] for mac in brd_dst_macs}
                
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
