#!/bin/bash
set -e

# Create Python venv and install pip packages from requirements.txt
python3 -m venv .venv_pi
source .venv_pi/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "Virtual environment created at .venv_pi and packages installed."
