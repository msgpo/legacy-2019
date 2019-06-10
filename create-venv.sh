#!/usr/bin/env bash
set -e

this_dir="$( cd "$( dirname "$0" )" && pwd )"
venv="${this_dir}/.venv"

rm -rf "${venv}"

echo "Creating virtual environment at ${venv}"
python3 -m venv "${venv}"

echo "Installing libraries"
source "${venv}/bin/activate"
python3 -m pip install wheel
python3 -m pip install -r requirements.txt

echo "OK"
