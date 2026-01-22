#!/bin/bash
cd "$(dirname "$0")"
cd ..
source venv/bin/activate
python scripts/unified_importer.py
