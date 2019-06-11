#!/usr/bin/env bash
set -e

this_dir="$( cd "$( dirname "$0" )" && pwd )"
venv="${this_dir}/.venv"

if [[ ! -d "${venv}" ]]; then
    echo "Missing virtual environment at ${venv}. Please run create-venv.sh"
    exit 1
fi

source "${venv}/bin/activate"

python3 game_gui.py "$@"
