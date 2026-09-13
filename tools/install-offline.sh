#!/bin/sh
# The CI bundle wheelhouse targets CPython 3.11, Linux x86-64, CPU.
set -eu
cd "$(dirname "$0")/.."
python3.11 -m venv .venv
.venv/bin/pip install --no-index --find-links wheelhouse torch==2.8.0+cpu torchvision==0.23.0+cpu -r requirements.txt
.venv/bin/python -c 'from reapergrasp.model import verify_bundle; verify_bundle("models/version_1")'
echo 'Run .venv/bin/python -m reapergrasp'
