"""Verify the complete imported HMigBot payload and record transparent derivative edits."""
import argparse
import hashlib
import json
from pathlib import Path
from manage_install import filesystem_path

ROOT = filesystem_path(Path(__file__).resolve().parents[1])


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def audit():
    baseline = json.loads((ROOT / 'docs/upstream/import-manifest.json').read_text(encoding='utf-8'))
    changed, missing, binaries_changed = [], [], []
    for entry in baseline['files']:
        path = ROOT / 'vendor/hmigbot' / entry['path']
        if not path.is_file():
            missing.append(entry['path'])
            continue
        current = digest(path)
        if current != entry['sha256']:
            changed.append({'path': entry['path'], 'upstream_sha256': entry['sha256'], 'current_sha256': current})
            if '/scripts/bin/' in entry['path'] or path.suffix in {'.exe', '.dll', '.bin', '.so', '.dylib'}:
                binaries_changed.append(entry['path'])
    return {'upstream_version': baseline['version'], 'imported_files': len(baseline['files']),
            'unchanged_files': len(baseline['files']) - len(changed) - len(missing),
            'changes': changed, 'missing': missing, 'binaries_changed': binaries_changed,
            'status': 'passed' if not missing and not binaries_changed else 'failed',
            'scope': 'Complete original resources bundled in vendor/hmigbot, outside the active skill discovery tree'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='Refresh reviewed derivative manifest after edits')
    args = parser.parse_args()
    result = audit()
    path = ROOT / 'docs/upstream/derivative-manifest.json'
    if args.write:
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    else:
        expected = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
        result['manifest_matches'] = expected == result
        if not result['manifest_matches']:
            result['status'] = 'failed'
    print(json.dumps({key: value for key, value in result.items() if key != 'changes'}, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
