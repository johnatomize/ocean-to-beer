#!/bin/zsh
set -e
cd -- "$(dirname -- "$0")"
/usr/bin/python3 render.py "$@"
printf '\nFinished. The MP4 is in the output folder.\n'
