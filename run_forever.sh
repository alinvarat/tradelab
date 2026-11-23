#!/bin/bash
# Keeps server.py running: restarts it 5 seconds after any exit until this script is stopped.
cd "$(dirname "$0")" || exit 1
while true; do
    python3 -u server.py >> server.log 2>&1
    echo "$(date +%T) server exited with $?; restarting" >> server.log
    sleep 5
done
