"""Exact production nginx + loopback stub: no live backend, identity or ASR."""
import argparse
import base64
import io
import json
import re
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from uuid import uuid4


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--image', default='mirror.gcr.io/nginxinc/nginx-unprivileged:1.27-alpine@sha256:65e3e85dbaed8ba248841d9d58a899b6197106c23cb0ff1a132b7bfe0547e4c0')
    cli.add_argument('--config', type=Path, default=Path('deploy/nginx.conf'))
    cli.add_argument('--output', type=Path, default=Path('output/ai-voice-ingress.json'))
    args = cli.parse_args()
    image = subprocess.check_output(['docker', 'image', 'inspect', '--format', '{{.Id}}', args.image], text=True).strip()
    assert re.fullmatch(r'sha256:[0-9a-f]{64}', image)
    name = 'ttest-voice-ingress-' + uuid4().hex[:12]
    rows = []
    with tempfile.TemporaryDirectory(prefix='ttest-voice-ingress-') as folder:
        config = Path(folder) / 'production.conf'
        config.write_bytes(args.config.read_bytes())
        config.chmod(0o644)  # Match Dockerfile COPY --chmod=644, including root-only checkouts.
        stub = Path(folder) / 'stub.conf'
        stub.write_text('server { listen 8000; access_log off; error_log /dev/null; location / { return 200 "fixture"; } }\n')
        stub.chmod(0o644)
        command = ['docker', 'run', '--detach', '--name', name, '--label', 'es.ttest.purpose=voice-ingress-regression',
                   '--network', 'none', '--read-only', '--log-driver', 'none', '--cap-drop', 'ALL',
                   '--security-opt', 'no-new-privileges:true', '--tmpfs', '/tmp', '--tmpfs', '/var/cache/nginx',
                   '--tmpfs', '/var/run', '--add-host', 'backend:127.0.0.1',
                   '--mount', f'type=bind,src={config},dst=/etc/nginx/conf.d/default.conf,readonly',
                   '--mount', f'type=bind,src={stub},dst=/etc/nginx/conf.d/stub.conf,readonly',
                   '--entrypoint', 'nginx', image, '-g', 'daemon off;']
        syntax = subprocess.run([arg for arg in command[:-2] if arg != '--detach'] + ['-t'], capture_output=True, text=True)
        if syntax.returncode:
            # The owned container has no live data and logs only public config errors.
            subprocess.run(['docker', 'rm', '--force', name], capture_output=True)
            raise RuntimeError('FIXTURE_CONFIG_INVALID ' + syntax.stderr[-1500:])
        subprocess.run(['docker', 'rm', '--force', name], check=True, capture_output=True)
        subprocess.run(command, check=True, capture_output=True)
        try:
            for _ in range(30):
                ready = subprocess.run(['docker', 'exec', name, 'wget', '-q', '-O', '/dev/null', 'http://127.0.0.1:8000/'], capture_output=True)
                if ready.returncode == 0:
                    break
                time.sleep(.1)
            else:
                raise RuntimeError('FIXTURE_NGINX_NOT_READY ' + ready.stderr.decode(errors='replace')[-500:])

            def post(label, payload, wanted, path='/api/v1/ai-search/voice'):
                shell = 'cat > /tmp/fixture-body; wget -S -O /dev/null --header="Content-Type: application/json" --post-file=/tmp/fixture-body http://127.0.0.1:8080' + path + ' 2>&1'
                response = subprocess.run(['docker', 'exec', '-i', name, 'sh', '-c', shell], input=payload, capture_output=True, timeout=15)
                statuses = re.findall(rb'HTTP/\d\.\d (\d{3})', response.stdout + response.stderr)
                actual = int(statuses[-1]) if statuses else None
                rows.append({'case': label, 'body_bytes': len(payload), 'expected_http': wanted, 'actual_http': actual})

            for seconds in (5, 7, 15):
                data = io.BytesIO()
                with wave.open(data, 'wb') as wav:
                    wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                    wav.writeframes(bytes(seconds * 32000))
                body = {'idempotency_key': str(uuid4()), 'session_id': str(uuid4()), 'expected_version': 0,
                        'media_type': 'audio/wav', 'audio_base64': base64.b64encode(data.getvalue()).decode(), 'search': {'limit': 6}}
                post(f'whole-{seconds}s-pcm-wav', json.dumps(body, separators=(',', ':')).encode(), 200)
            post('voice-exact-boundary', b' ' * 650000, 200)
            post('voice-over-boundary', b' ' * 650001, 413)
            post('ordinary-api-bound-unchanged', b' ' * 300000, 413, '/api/v1/fixture')
        finally:
            # Only the owned named fixture is removed; it has no host ports or data volumes.
            subprocess.run(['docker', 'rm', '--force', name], check=True, capture_output=True)
    result = {'method': 'Exact production nginx config, network-none container, loopback200 upstream stub.', 'nginx_image': image,
              'cases': rows, 'all_passed': all(row['actual_http'] == row['expected_http'] for row in rows),
              'live_queries': 0, 'identities': 0, 'asr_calls': 0}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    assert result['all_passed'], 'PRIMARY_VOICE_INGRESS_BODY_LIMIT_MISMATCH'


if __name__ == '__main__':
    main()
