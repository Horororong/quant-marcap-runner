"""Shared deterministic, atomic CSV publication (no collector side effects)."""

import csv
import gzip
import io
import os
import tempfile
from pathlib import Path

import pandas as pd


def canonical_csv(payload: bytes, ignore_columns=()) -> bytes:
    """Sort CSV fields/rows without interpreting amounts, codes or missing tokens."""
    rows = list(csv.reader(io.StringIO(payload.decode('utf-8-sig'), newline='')))
    if not rows:
        return b''
    header, data = rows[0], rows[1:]
    order = sorted((i for i, name in enumerate(header) if name not in ignore_columns),
                   key=lambda i: header[i])
    if any(len(row) != len(header) for row in data):
        raise ValueError('Malformed CSV row width')
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow([header[i] for i in order])
    writer.writerows(sorted(tuple(row[i] for i in order) for row in data))
    return stream.getvalue().encode('utf-8-sig')


def atomic_write_if_changed(frame: pd.DataFrame, path: Path, *, ignore_columns=()) -> bool:
    """Keep old bytes on an equivalent refresh; atomically publish real changes."""
    path = Path(path)
    payload = canonical_csv(frame.to_csv(index=False, lineterminator='\n').encode('utf-8-sig'))
    compressed = path.suffix == '.gz'
    if path.exists():
        previous = path.read_bytes()
        previous_csv = gzip.decompress(previous) if compressed else previous
        comparison = canonical_csv(payload, ignore_columns) if ignore_columns else payload
        if canonical_csv(previous_csv, ignore_columns) == comparison:
            return False
    if compressed:
        stream = io.BytesIO()
        # Explicitly omit FNAME; using a destination path as filename changes bytes.
        with gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0, compresslevel=9) as archive:
            archive.write(payload)
        payload = stream.getvalue()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return True


