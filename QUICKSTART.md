# EtherLink Quick Start Guide

## Terminal 1: Your Machine - VSwitch Server
```bash
cd ~/Projects/networking/EtherLink
export AUTH_TOKEN_HEX="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0"
python3 vswitch.py 9999
```

**Expected Output:**
```
[VSwitch] Started at 0.0.0.0:9999
```

Keep this running.

---

## Terminal 2: Your Machine - VPort Client
```bash
cd ~/Projects/networking/EtherLink
export AUTH_TOKEN_HEX="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0"
sudo ./vport localhost 9999
```

**Expected Output:**
```
[VPort] TAP device name: tapyuan, VSwitch: localhost:9999
[VPort] Sent to VSwitch: dhost<...> shost<...> type<...> datasz<...>
```

Keep this running.

---

## Terminal 3: Your Machine - Configure TAP Interface
```bash
sudo ip addr add 10.1.1.101/24 dev tapyuan
sudo ip link set tapyuan up
ip addr show tapyuan
```

**Expected Output:**
```
3: tapyuan: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 10.1.1.101/24 scope global tapyuan
```

---

## Terminal 4: Kali VM - SSH & Setup
```bash
ssh user@<KALI_IP>
cd /tmp
git clone <REPO_URL> EtherLink
cd EtherLink
make clean && make
```

Replace:
- `<KALI_IP>` = Your Kali VM IP (e.g., 192.168.1.50)
- `<REPO_URL>` = EtherLink repository URL

---

## Terminal 5: Kali VM - VPort Client
```bash
cd /tmp/EtherLink
export AUTH_TOKEN_HEX="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0"
sudo ./vport 192.168.29.216 9999
```

**Replace `192.168.1.100` with your machine's IP**

**Expected Output:**
```
[VPort] TAP device name: tapyuan, VSwitch: 192.168.1.100:9999
[VPort] Sent to VSwitch: dhost<...> shost<...> type<...> datasz<...>
```

Keep this running.

---

## Terminal 6: Kali VM - Configure TAP Interface
```bash
sudo ip addr add 10.1.1.102/24 dev tapyuan
sudo ip link set tapyuan up
ip addr show tapyuan
```

**Expected Output:**
```
3: tapyuan: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 10.1.1.102/24 scope global tapyuan
```

---

## Terminal 7: Your Machine - Test Ping to Kali
```bash
ping -c 4 10.1.1.102
```

**Expected Output:**
```
PING 10.1.1.102 (10.1.1.102) 56(84) bytes of data.
64 bytes from 10.1.1.102: icmp_seq=1 ttl=64 time=2.45 ms
64 bytes from 10.1.1.102: icmp_seq=2 ttl=64 time=2.15 ms
64 bytes from 10.1.1.102: icmp_seq=3 ttl=64 time=2.30 ms
64 bytes from 10.1.1.102: icmp_seq=4 ttl=64 time=2.25 ms
```

---

## Terminal 8: Kali VM - Test Ping to Your Machine
```bash
ping -c 4 10.1.1.101
```

**Expected Output:**
```
PING 10.1.1.101 (10.1.1.101) 56(84) bytes of data.
64 bytes from 10.1.1.101: icmp_seq=1 ttl=64 time=2.50 ms
64 bytes from 10.1.1.101: icmp_seq=2 ttl=64 time=2.20 ms
64 bytes from 10.1.1.101: icmp_seq=3 ttl=64 time=2.35 ms
64 bytes from 10.1.1.101: icmp_seq=4 ttl=64 time=2.28 ms
```

---

## Monitoring Real-Time Output

Watch vswitch in Terminal 1:
- Should show frame forwarding logs
- Should learn MAC addresses
- Should show broadcast handling

Watch vport in Terminal 2 & 5:
- Should show "Sent to VSwitch" messages
- Should show "Forward to TAP device" messages

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Cannot find device "tapyuan"` | vport didn't start. Check Terminal 2/5 output |
| `Connection refused` | vswitch not running. Check Terminal 1 |
| `Auth failed` | Token mismatch. Ensure same `AUTH_TOKEN_HEX` everywhere |
| `No response to ping` | Check TAP interfaces are UP: `ip link show tapyuan` |
| `Permission denied` | Use `sudo` for ip and vport commands |

---

## What's Being Tested

✅ **Authentication** - Token-based challenge-response  
✅ **Frame Forwarding** - Packets routed between TAP interfaces  
✅ **MAC Learning** - vswitch learns source MAC → sender IP mapping  
✅ **Input Validation** - Frame size and format checking  
✅ **MAC Aging** - Stale entries cleaned up automatically  
✅ **Reliability** - Sustained packet flow without crashes  

---

## Architecture Diagram

```
Your Machine                    Kali VM
    │                               │
    ├─ App Layer                    ├─ App Layer
    │                               │
    ├─ TAP 10.1.1.101               ├─ TAP 10.1.1.102
    │      │                              │
    ├─ VPort ◄─────── UDP ──────────► VPort
    │      │         Port 9999            │
    └──────────────────────────────────────┘
              │
              ├─ VSwitch (localhost:9999)
              │  - MAC Learning
              │  - Frame Forwarding
              │  - Input Validation
              └─ Frame Aging (30 min timeout)
```

---

## Commands at a Glance

| Component | Command | IP |
|-----------|---------|-----|
| VSwitch | `python3 vswitch.py 9999` | N/A |
| Your VPort | `sudo ./vport localhost 9999` | 10.1.1.101 |
| Kali VPort | `sudo ./vport 192.168.1.100 9999` | 10.1.1.102 |
| Ping Your → Kali | `ping 10.1.1.102` | - |
| Ping Kali → Your | `ping 10.1.1.101` | - |

---

**Ready to test? Start with Terminal 1!**
