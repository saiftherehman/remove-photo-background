#!/bin/sh
# Starts Photo Background on Linux. Double-click it, or run ./run_linux.sh
cd "$(dirname "$(readlink -f "$0")")" || exit 1

# Use the newest Python 3 on the system. On RHEL / CentOS / Rocky the plain
# "python3" can be too old, while python3.11 or python3.12 is installed next to it.
PY=""
for p in python3.14 python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
    if command -v "$p" >/dev/null 2>&1 &&
       "$p" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
        PY="$p"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "Python 3.9 or newer is not installed. Install it with your package manager:"
    echo "  Debian / Ubuntu / Mint:   sudo apt install python3 python3-pip"
    echo "  Fedora:                   sudo dnf install python3 python3-pip"
    echo "  RHEL / CentOS / Rocky 8+: sudo dnf install python3.11 python3.11-pip"
    echo "  Arch / Manjaro:           sudo pacman -S python python-pip"
    echo "  openSUSE:                 sudo zypper install python3 python3-pip"
    printf "Press Enter to close."; read _
    exit 1
fi

"$PY" photo_background.py "$@" || { echo; printf "Something went wrong. Press Enter to close."; read _; }
