"""Render only a literal verified Traefik peer, never a network-wide trust rule."""
import argparse
from ipaddress import IPv4Address
from pathlib import Path


def render(template, peer):
    address = IPv4Address(peer)
    if address.is_unspecified or address.is_multicast or address.is_loopback:
        raise ValueError("verified Traefik IPv4 peer required")
    return template.replace("__TRAEFIK_IP__", str(address))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--peer", required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(render(args.template.read_text(), args.peer))
