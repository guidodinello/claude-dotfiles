#!/bin/bash
# usage: fb.sh <handle> <text>  -> selects option 3 (Tell Claude what to change), types feedback, submits
orca terminal send --terminal "$1" --text "3" --json >/dev/null; sleep 1
orca terminal send --terminal "$1" --text "$2" --json >/dev/null; sleep 1
orca terminal send --terminal "$1" --text "" --enter --json | python3 -I -c "import json,sys;d=json.load(sys.stdin);print('sent',d.get('ok'),d.get('error'))"
