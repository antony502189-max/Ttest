"""Generate VAPID settings into a private environment file without printing keys."""
import argparse
import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--subject', default='mailto:noreply@112233.es')
    args = parser.parse_args()
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    private = key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip('=')
    path = Path(args.output)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as output:
        output.write(f'WEB_PUSH_PUBLIC_KEY={encode(public)}\nWEB_PUSH_PRIVATE_KEY={encode(private)}\nWEB_PUSH_SUBJECT={args.subject}\n')
    print(f'VAPID settings saved to {path}. Keep this file private.')


if __name__ == '__main__':
    main()
