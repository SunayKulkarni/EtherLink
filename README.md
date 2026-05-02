# Layer 2 Virtual Private Network

A custom-built Layer 2 VPN solution that creates a virtual network switch, enabling devices across the internet to communicate as if they're on the same local area network. Built from scratch using raw sockets and TAP devices.

## Features

- **Layer 2 Ethernet Bridging**: Operates at the data link layer, forwarding Ethernet frames between connected clients
- **MAC Address Learning**: Automatically learns and maintains a forwarding table for efficient packet delivery
- **Cross-Platform Connectivity**: Connect devices from anywhere in the world into a single virtual LAN
- **Lightweight**: Minimal dependencies - just Python and C
- **Serverless Option**: Works with Playit.gg for NAT traversal without requiring a dedicated server

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Virtual Switch                             │
│                                                                    │
│    ┌────────────────────────────────────────────┐                 │
│    │              MAC Forwarding Table          │                 │
│    │  ┌──────────────────┬──────────────────┐   │                 │
│    │  │    MAC Address   │   Virtual Port   │   │                 │
│    │  ├──────────────────┼──────────────────┤   │                 │
│    │  │ aa:bb:cc:dd:ee:01│   Client-1       │   │                 │
│    │  │ aa:bb:cc:dd:ee:02│   Client-2       │   │                 │
│    │  └──────────────────┴──────────────────┘   │                 │
│    └────────────────────────────────────────────┘                 │
│                          │                                         │
└──────────────────────────┼─────────────────────────────────────────┘
                           │
           ┌───────────────┴───────────────┐
           │                               │
           ▼                               ▼
┌─────────────────────┐         ┌─────────────────────┐
│     Client A        │         │     Client B        │
│                     │         │                     │
│  ┌───────────────┐  │         │  ┌───────────────┐  │
│  │  Application  │  │         │  │  Application  │  │
│  └───────┬───────┘  │         │  └───────┬───────┘  │
│          │          │         │          │          │
│  ┌───────┴───────┐  │         │  ┌───────┴───────┐  │
│  │ TAP Interface │  │         │  │ TAP Interface │  │
│  │  10.1.1.101   │  │         │  │  10.1.1.102   │  │
│  └───────┬───────┘  │         │  └───────┬───────┘  │
│          │          │         │          │          │
│  ┌───────┴───────┐  │         │  ┌───────┴───────┐  │
│  │  VPort Agent  │  │         │  │  VPort Agent  │  │
│  └───────┬───────┘  │         │  └───────┴───────┘  │
└──────────┼──────────┘         └──────────┼──────────┘
           │                               │
           └───────────────┬───────────────┘
                           │
                    ┌──────┴──────┐
                    │  Playit.gg  │
                    │   Tunnel    │
                    └─────────────┘
```

## Technical Components

| Component          | Language | Description                                                 |
| ------------------ | -------- | ----------------------------------------------------------- |
| **Virtual Switch** | Python   | Core switching logic with MAC learning and frame forwarding |
| **VPort Agent**    | C        | Low-level TAP device management and UDP transport           |
| **TAP Interface**  | Kernel   | Virtual Layer 2 network interface                           |

## Quick Start

### Server (with Playit.gg)

```bash
# Start Playit tunnel (UDP, port 9999)
playit

# Start Virtual Switch
python3 vswitch.py 9999

# Connect locally
sudo ./vport localhost 9999
sudo ip addr add 10.1.1.101/24 dev tapyuan
sudo ip link set tapyuan up
```

### Client

```bash
sudo ./vport YOUR_PLAYIT_ADDRESS PORT
sudo ip addr add 10.1.1.102/24 dev tapyuan
sudo ip link set tapyuan up

# Test
ping 10.1.1.101
```

## File Transfer Demo

Once both TAP interfaces can ping each other, you can demonstrate application traffic by sending a file over the virtual LAN with the included TCP helper script.

### Receiver

```bash
python3 file_transfer_demo.py receive 10.1.1.101 5000 received.bin
```

### Sender

```bash
python3 file_transfer_demo.py send 10.1.1.101 5000 demo.bin
```

The script prints the transferred byte count and SHA256 hash on both sides so you can verify that the file arrived intact.

## Technical Highlights

- **Raw Socket Programming**: Direct manipulation of Ethernet frames at Layer 2
- **Virtual Network Interfaces**: TAP device implementation for OS-level network integration
- **Concurrent I/O**: Event-driven architecture handling multiple clients
- **Network Address Learning**: Dynamic MAC table with automatic discovery
- **UDP Encapsulation**: Custom protocol for frame transport across the internet
