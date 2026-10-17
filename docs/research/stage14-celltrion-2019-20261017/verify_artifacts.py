"""Verify final Stage14 byte pins, without financial parsing or network."""
import hashlib
import json
from pathlib import Path
HOME=Path(__file__).resolve().parent
ROOT=HOME.parents[2]
if __name__=='__main__':
    pins=json.loads((HOME/'artifact_manifest.json').read_text())['files']
    for name,pin in pins.items():
        raw=(ROOT/name).read_bytes()
        assert len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256'],name
    print(json.dumps(dict(status='PASS_IDENTICAL_BYTES',files=len(pins),real_event_verdict='UNVERIFIED',investment_approved=False)))
