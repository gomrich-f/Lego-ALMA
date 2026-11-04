#!/bin/bash
set -e

# Install common system dependencies useful for scientific Python and OpenCV
sudo apt-get update
sudo apt-get install -y build-essential python3-dev python3-venv libatlas-base-dev libjpeg-dev libpng-dev libavcodec-dev libavformat-dev libswscale-dev libv4l-dev libgtk-3-dev gfortran

echo "System dependencies installed."
