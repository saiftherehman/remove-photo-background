#!/bin/sh
# Starts Photo Background on macOS. Double-click it in Finder.
cd "$(dirname "$0")" || exit 1

if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
    echo "Python 3.9 or newer is not installed."
    echo "Download it from https://www.python.org/downloads/macos/ and run this again."
    printf "Press Enter to close."; read _
    exit 1
fi

python3 photo_background.py "$@" || { echo; printf "Something went wrong. Press Enter to close."; read _; }
