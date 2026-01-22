#!/bin/bash
# Script to run the unified importer with the virtual environment

# Change to the project directory
cd "$(dirname "$0")/.."

# Activate the virtual environment
source venv/bin/activate

# Run the Python script
python3 scripts/unified_importer.py

# Deactivate the virtual environment
deactivate