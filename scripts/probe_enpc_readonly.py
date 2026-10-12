"""Probe ENPC UDP reachability with the read-only 'N' command.

The XB22Q5 handler at nwsoc address 0x1bbbbc only constructs a response.
No configuration field is supplied or written by this request.
"""
import argparse
import socket


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('address', help='Printer IPv4 address')
    parser.add_argument('--timeout', type=float, default=3)
    args = parser.parse_args()
    request = b'EPSON' + b'N' + b'\x00' * 9
    assert len(request) == 15
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(args.timeout)
        sock.sendto(request, (args.address, 3289))
        try:
            response, peer = sock.recvfrom(128)
        except socket.timeout:
            print('No response')
            return 1
    print(f'Source: {peer[0]}:{peer[1]}')
    print(f'Length: {len(response)}')
    print(f'Header: {response[:16].hex()}')
    if peer != (args.address, 3289) or not response.startswith(b'EPSONn'):
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
