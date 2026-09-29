"""Invoke a bundled, source-neutral HMigBot helper."""
from pathlib import Path
import json, subprocess, sys
here = Path(__file__).resolve()
skill = next(p for p in here.parents if (p / 'SKILL.md').is_file())
runtime = skill / 'runtime.json'
root = (skill / json.loads(runtime.read_text())['runtime_relative']).resolve() if runtime.exists() else skill.parents[1]
helper = root / 'vendor/hmigbot' / 'skills/arkts-visual-verify/scripts/incremental_verify.py'
if not helper.is_file(): raise SystemExit('Bundled helper missing; reinstall the complete plugin')
raise SystemExit(subprocess.run([sys.executable, str(helper), *sys.argv[1:]], shell=False).returncode)
