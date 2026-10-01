"""Networked build-time preparation; sandbox bootstrap itself never downloads."""
import argparse
from pathlib import Path
import subprocess
import sys
from build_sandbox_kit import ROOT, read_lock, locked_wheels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--runtime-target', action='append', choices=('cp311', 'cp312'))
    args = parser.parse_args()
    for abi in args.runtime_target or ('cp311', 'cp312'):
        lock = ROOT / f'config/sandbox/requirements-{abi}-linux-x86_64.lock'
        dest = args.output_dir / abi
        dest.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, '-m', 'pip', '--isolated', 'download', '--index-url', 'https://pypi.org/simple',
                        '--only-binary=:all:', '--no-deps', '--require-hashes', '--python-version', f'3.{abi[3:]}',
                        '--implementation', 'cp', '--abi', abi, '--platform', 'manylinux_2_28_x86_64',
                        '--platform', 'manylinux_2_27_x86_64', '--platform', 'manylinux2014_x86_64',
                        '--dest', str(dest), '-r', str(lock)], check=True)
        locked_wheels(dest, read_lock(lock))
        print(f'{abi}: locked wheel hashes verified')


if __name__ == '__main__':
    main()
