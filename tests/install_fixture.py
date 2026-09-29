"""Small installer payload for ownership tests; full ZIP smoke covers every binary."""
from unittest.mock import patch


def small_payload(installer):
    full = installer.payload()
    selected = {}
    for name, data in full.items():
        if '/skills/' in name:
            if not any('/skills/' + skill + '/' in name for skill in
                       ('a2h-run', 'ios-source-analysis', 'ios-resources-convert', 'ios-ui-to-arkui')):
                continue
            if '/bin/' in name:
                continue
        elif '/bin/' in name:
            continue
        selected[name] = data
    return patch.object(installer, 'payload', return_value=selected)
