#!/bin/bash
# usage: tread.sh <handle> [lines]
N=${2:-60}
L=$(orca terminal read --terminal "$1" --json | python3 -I -c "import json,sys;print(json.load(sys.stdin)['result']['terminal']['latestCursor'])")
C=$(( L > N*4 ? L - N*4 : 0 ))
orca terminal read --terminal "$1" --cursor $C --limit 5000 --json | python3 -I -c "
import json,sys,re
t=json.load(sys.stdin)['result']['terminal']['tail']
t=[l.rstrip() for l in t if l.strip() and not re.match(r'^[·✢✳✶✻✽*]\s*\S+…',l.strip())]
print('\n'.join(t[-int(sys.argv[1]):]))" "$N"
