"""Disposable nginx mTLS regression; no backend/provider/real keys or image pull."""
import argparse
import hashlib
import json
import ssl
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def certificate(directory, name, *, issuer=None, client=False):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "DISPOSABLE-" + name)])
    now = datetime.now(UTC)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(issuer[0].subject if issuer else subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(hours=1))
            .add_extension(x509.BasicConstraints(ca=issuer is None, path_length=0 if issuer is None else None), True))
    if issuer:
        cert = cert.add_extension(x509.ExtendedKeyUsage([
            ExtendedKeyUsageOID.CLIENT_AUTH if client else ExtendedKeyUsageOID.SERVER_AUTH]), False)
    cert = cert.sign(issuer[1] if issuer else key, hashes.SHA256())
    (directory / (name + ".crt")).write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (directory / (name + ".key")).write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return cert, key


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--image", required=True)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    if not args.image.startswith("sha256:") or len(args.image) != 71:
        raise ValueError("Existing immutable image ID required")
    directory = args.output.resolve()
    directory.mkdir(exist_ok=False, parents=True)
    ca = certificate(directory, "client-ca")
    certificate(directory, "localhost", issuer=ca)
    certificate(directory, "operator", issuer=ca, client=True)
    wrong = certificate(directory, "untrusted-ca")
    certificate(directory, "untrusted", issuer=wrong, client=True)
    (directory / "proxy.conf").write_text('proxy_set_header X-AI-Lab-Access "' + "a" * 64 + '";\n')
    config = Path(__file__).resolve().parents[1] / "deploy/ai-text-lab/closed-ui.nginx.conf"
    name = "ttest-pr404-mtls-" + uuid4().hex[:12]
    def docker(*items):
        return subprocess.check_output(["docker", *items], text=True, timeout=30).strip()
    started = False
    try:
        docker("run", "-d", "--rm", "--pull=never", "--name", name,
               "--label", "es.ttest.purpose=pr404-disposable-mtls-regression",
               "--add-host", "backend:127.0.0.1", "-p", "127.0.0.1::8443",
               "--mount", f"type=bind,source={directory},target=/lab-tls,readonly",
               "--mount", f"type=bind,source={directory},target=/closed-ui-access,readonly",
               "--mount", f"type=bind,source={config},target=/etc/nginx/conf.d/default.conf,readonly", args.image)
        started = True
        inspected = json.loads(docker("inspect", name))[0]
        port = inspected["NetworkSettings"]["Ports"]["8443/tcp"][0]["HostPort"]
        origin = f"https://127.0.0.1:{port}"
        docker("exec", name, "nginx", "-t")
        statuses = {}
        for actor in ("anonymous", "untrusted", "operator"):
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE  # Known disposable loopback server.
            if actor != "anonymous":
                context.load_cert_chain(directory / (actor + ".crt"), directory / (actor + ".key"))
            for attempt in range(20):
                try:
                    with httpx.Client(verify=context, trust_env=False, timeout=2) as client:
                        statuses[actor] = client.get(origin).status_code
                    break
                except httpx.ConnectError:
                    if attempt == 19:
                        raise
                    time.sleep(.1)
        assert statuses == {"anonymous": 400, "untrusted": 400, "operator": 200}, statuses
        report = {"schema": "ai-lab-mtls-regression.v1", "statuses": statuses,
                  "nginxImage": inspected["Image"],
                  "configurationSha256": hashlib.sha256(config.read_bytes()).hexdigest(),
                  "providerCalls": 0, "backendStarted": False, "realCredentialsMounted": False}
        (directory / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))
    finally:
        if started:
            docker("stop", name)


if __name__ == "__main__":
    main()
