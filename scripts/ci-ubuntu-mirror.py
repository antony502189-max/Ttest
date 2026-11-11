"""Use Ubuntu's canonical archive for CI instead of the Azure cloud mirror.

Only the mirror URI changes. Playwright still installs every dependency and
APT still verifies the distribution's signed metadata with existing keys.
"""
import os
import re
from pathlib import Path

CLOUD = re.compile(r'https?://azure\.archive\.ubuntu\.com/ubuntu(?=/|\s|$)')

def normalize(apt: Path) -> list[str]:
    apt = apt.resolve()
    files = [apt / 'sources.list', *(apt / 'sources.list.d').glob('*.list'),
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
