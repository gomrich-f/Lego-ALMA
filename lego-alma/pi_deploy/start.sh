#!/bin/bash
set -e

# Activate venv and start the main program
if [ ! -d ".venv_pi" ]; then
  echo "Virtualenv .venv_pi not found. Run ./setup_pi.sh first."
  exit 1
fi

source .venv_pi/bin/activate
python3 ../la_main.py
