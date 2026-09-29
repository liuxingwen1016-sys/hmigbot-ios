"""Audit maintained instruction entrypoints; separately disclose the intact archive."""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
LEGACY = re.compile(r'android|安卓|kotlin|gradle|(?<![A-Za-z])adb(?![A-Za-z])|Jetpack|AppCompat|'
                    r'Intent\.ACTION_|DialogFragment|setContentView|findViewById|res/layout', re.I)
TEXT = {'.md', '.py', '.js', '.json', '.toml', '.yaml', '.yml', '.ps1', '.sh', ''}


def audit(root=ROOT):
    files, findings = [], []
    for folder in ('skills', 'agents-codex', 'bin'):
        for path in (root / folder).rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts or path.suffix not in TEXT:
                continue
            try:
                text = path.read_text(encoding='utf-8-sig')
            except UnicodeDecodeError:
                continue
            files.append(path.relative_to(root).as_posix())
            for i, line in enumerate(text.splitlines(), 1):
                if LEGACY.search(line):
                    findings.append({'path': files[-1], 'line': i, 'text': line[:260]})
    retired = json.loads((root / 'docs/upstream/retired-skills.json').read_text(encoding='utf-8'))
    for name in retired:
        if (root / 'skills' / name / 'SKILL.md').exists():
            findings.append({'path': f'skills/{name}', 'rule': 'retired-source-skill-discoverable'})
    return {'status': 'passed' if not findings else 'failed', 'files_scanned': len(files),
            'findings': findings, 'scope': 'All maintained skills, references, templates, roles and text entrypoints',
            'archive': 'vendor/hmigbot contains 3516 byte-identical original resources, outside active discovery; original platform names are retained there',
            'other_occurrences': 'Historical documentation and negative compatibility tests retain truthful names. This lexical gate does not prove semantic or application equivalence.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit()
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8')
    print(text)
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
