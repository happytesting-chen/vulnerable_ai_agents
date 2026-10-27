"""Export only explicit target files, without development history or answers."""
import argparse
import hashlib
import json
from pathlib import Path

FILES = ('agent.py', 'Dockerfile', '.dockerignore', 'README.md', 'LICENSE')


def export(destination):
    source = Path(__file__).resolve().parents[1] / 'targets' / 'research_assistant'
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for name in FILES:
        data = (source / name).read_bytes()
        (destination / name).write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    return hashes


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('destination', type=Path)
    args = p.parse_args()
    print(json.dumps(export(args.destination), indent=2))
