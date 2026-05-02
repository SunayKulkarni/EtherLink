#!/usr/bin/env python3

import argparse
import hashlib
import os
import socket
import sys

CHUNK_SIZE = 64 * 1024


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as infile:
        while True:
            chunk = infile.read(CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def receive_file(listen_ip, port, output_path):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((listen_ip, port))
        server_sock.listen(1)
        print(f"[Receiver] Listening on {listen_ip}:{port}")

        conn, addr = server_sock.accept()
        with conn, open(output_path, "wb") as outfile:
            print(f"[Receiver] Connection from {addr[0]}:{addr[1]}")
            total = 0
            while True:
                chunk = conn.recv(CHUNK_SIZE)
                if not chunk:
                    break
                outfile.write(chunk)
                total += len(chunk)

    print(f"[Receiver] Saved {total} bytes to {output_path}")
    print(f"[Receiver] SHA256 {sha256_file(output_path)}")


def send_file(server_ip, port, input_path):
    filesize = os.path.getsize(input_path)
    digest = sha256_file(input_path)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_sock:
        client_sock.connect((server_ip, port))
        print(f"[Sender] Connected to {server_ip}:{port}")
        total = 0

        with open(input_path, "rb") as infile:
            while True:
                chunk = infile.read(CHUNK_SIZE)
                if not chunk:
                    break
                client_sock.sendall(chunk)
                total += len(chunk)

    print(f"[Sender] Sent {total} bytes from {input_path}")
    print(f"[Sender] Expected size {filesize} bytes")
    print(f"[Sender] SHA256 {digest}")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Minimal TCP file transfer demo for EtherLink TAP networks."
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    receive_parser = subparsers.add_parser(
        "receive", help="Listen for a single inbound file transfer."
    )
    receive_parser.add_argument("listen_ip", help="Local TAP IP to bind to.")
    receive_parser.add_argument("port", type=int, help="TCP port to listen on.")
    receive_parser.add_argument("output_path", help="Path to save the received file.")

    send_parser = subparsers.add_parser(
        "send", help="Send a file to a receiver over the EtherLink network."
    )
    send_parser.add_argument("server_ip", help="Receiver TAP IP address.")
    send_parser.add_argument("port", type=int, help="Receiver TCP port.")
    send_parser.add_argument("input_path", help="Path to the file to send.")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.mode == "receive":
            receive_file(args.listen_ip, args.port, args.output_path)
        else:
            send_file(args.server_ip, args.port, args.input_path)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
