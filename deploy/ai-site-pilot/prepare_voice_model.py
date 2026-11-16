"""Download pinned model assets, never user audio. Run only at image build time."""
import hashlib
from pathlib import Path
from urllib.request import urlopen

REVISION = "536b0662742c02347bc0e980a01041f333bce120"
FILES = {
    "model.bin": "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671",
    "config.json": "b55496ac7940a7ae47d2c01eab40edfd8701feec1229d9cce3b40014383fb828",
    "tokenizer.json": "fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab",
    "vocabulary.txt": "34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913",
}


def main():
    root = Path("/opt/voice-model")
    root.mkdir(parents=True, exist_ok=False)
    for name, expected in FILES.items():
        path = root/name
        digest = hashlib.sha256()
        count = 0
        with urlopen(f"https://huggingface.co/Systran/faster-whisper-small/resolve/{REVISION}/{name}", timeout=60) as source, path.open("xb") as target:
            while chunk := source.read(1024*1024):
                count += len(chunk)
                if count > 500_000_000:
                    raise ValueError("MODEL_ASSET_TOO_LARGE")
                digest.update(chunk)
                target.write(chunk)
        if digest.hexdigest() != expected:
            raise ValueError("MODEL_ASSET_DIGEST_MISMATCH")
        path.chmod(0o444)
    root.chmod(0o555)


if __name__ == "__main__":
    main()
