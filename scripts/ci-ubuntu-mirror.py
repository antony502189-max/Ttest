"""Use Ubuntu's canonical archive for CI instead of the Azure cloud mirror.

Only the mirror URI changes. Playwright still installs every dependency and
APT still verifies the distribution's signed metadata with existing keys.
"""
import os
import re
import ipaddress
import json
import socket
import time
import urllib.request
from pathlib import Path

CLOUD = re.compile(r'https?://azure\.archive\.ubuntu\.com/ubuntu(?=/|\s|$)')
UBUNTU_HOSTS = ('archive.ubuntu.com', 'security.ubuntu.com')


def doh_addresses(host: str) -> list[str]:
    if host not in UBUNTU_HOSTS:
        raise ValueError('Only Ubuntu archive DNS may use this fallback')
    # Verified HTTPS with DNSSEC checking enabled; fixed public archive hosts only.
    # https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/make-api-requests/dns-json/
    url = f'https://cloudflare-dns.com/dns-query?name={host}&type=A'
    request = urllib.request.Request(url, headers={'Accept': 'application/dns-json'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                value = json.loads(response.read(65536))
            break
        except OSError:
            if attempt == 2:
                raise
            time.sleep(1)
    if (not isinstance(value, dict) or value.get('Status') != 0 or value.get('CD') is not False
            or not any(q.get('name', '').rstrip('.').lower() == host and q.get('type') == 1
                for q in value.get('Question', []))):
        raise ValueError('Ubuntu DNS fallback returned an invalid response')
    addresses = sorted({str(ipaddress.IPv4Address(r['data']))
        for r in value.get('Answer', []) if r.get('type') == 1})
    if not addresses or len(addresses) > 16 or not all(ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError('Ubuntu DNS fallback requires public IPv4 addresses')
    return addresses


def ensure_dns(hosts: Path, resolve=socket.getaddrinfo, lookup=doh_addresses) -> list[str]:
    before = hosts.read_text(encoding='utf-8')
    additions, fallback = [], []
    for host in UBUNTU_HOSTS:
        try:
            resolve(host, 443, socket.AF_INET)
        except OSError:
            for address in lookup(host):
                ip = ipaddress.IPv4Address(address)
                if not ip.is_global:
                    raise ValueError('Nonpublic Ubuntu DNS address rejected')
                line = f'{ip} {host} # ci-ubuntu-dns'
                if line not in before.splitlines():
                    additions.append(line)
            fallback.append(host)
    if additions:
        # Append only these two archive hosts; HTTPS and APT signatures still verify.
        with hosts.open('a', encoding='utf-8', newline='\n') as target:
            target.write(('' if before.endswith('\n') else '\n') + '\n'.join(additions) + '\n')
    return fallback

def normalize(apt: Path) -> list[str]:
    apt = apt.resolve()
    files = [apt / 'sources.list', apt / 'apt-mirrors.txt', *(apt / 'sources.list.d').glob('*.list'),
        *(apt / 'sources.list.d').glob('*.sources'), *(apt / 'mirrors').glob('*.list')]
    changed = []
    for path in files:
        if not path.is_file():
            continue
        if not path.resolve().is_relative_to(apt):
            raise RuntimeError('APT source escapes its configuration directory')
        before = path.read_text(encoding='utf-8')
        after = CLOUD.sub('https://archive.ubuntu.com/ubuntu', before)
        if after != before:
            path.write_text(after, encoding='utf-8', newline='\n')
            changed.append(str(path.relative_to(apt)))
    return changed

if __name__ == '__main__':
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise SystemExit('Only GitHub Actions runner configuration may be changed')
    print('Canonical Ubuntu mirror files:', ', '.join(normalize(Path('/etc/apt'))) or 'already configured')
    print('Ubuntu HTTPS DNS fallback:', ', '.join(ensure_dns(Path('/etc/hosts'))) or 'system DNS healthy')
