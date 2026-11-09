"""Download pinned model assets, never user audio. Run only at image build time."""
import hashlib
from pathlib import Path
from urllib.request import urlopen

REVISION = "d90ca5fe260221311c53c58e660288d3deb8d356"
FILES = {
    "model.bin": "dcb76c6586fc06cbdac6dd21f14cfd129cc4cdd9dce19bf4ffa62e59cbe6e6d1",
    "config.json": "a73a28cdfe1c43ccc7202fa333d1f89c202477271407ae9a7f19afa52039cac8",
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
        with urlopen(f"https://huggingface.co/Systran/faster-whisper-tiny/resolve/{REVISION}/{name}", timeout=60) as source, path.open("xb") as target:
            while chunk := source.read(1024*1024):
                count += len(chunk)
                if count > 150_000_000:
                    raise ValueError("MODEL_ASSET_TOO_LARGE")
                digest.update(chunk)
                target.write(chunk)
        if digest.hexdigest() != expected:
            raise ValueError("MODEL_ASSET_DIGEST_MISMATCH")
        path.chmod(0o444)
    root.chmod(0o555)


if __name__ == "__main__":
    main()
