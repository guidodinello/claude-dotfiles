#!/bin/bash
input=$(cat)

# Feed the same rate-limit JSON to herdr-agent-usage's cache (async, no display output of its own)
echo "$input" | bash /home/guido/.config/herdr/plugins/github/usagebar-33803b79d616/bin/run-statusline.sh >/dev/null 2>&1 &
disown 2>/dev/null || true

# Gentleman theme (ANSI 256)
PRIMARY='\033[38;5;110m'   # azul claro
ACCENT='\033[38;5;179m'    # dorado
MUTED='\033[38;5;242m'     # gris
SUCCESS='\033[38;5;150m'   # verde
WARN='\033[38;5;179m'      # amarillo/dorado
ERROR='\033[38;5;174m'     # rosa/rojo
PURPLE='\033[38;5;183m'    # púrpura
BOLD='\033[1m'
NC='\033[0m'

SEP="${MUTED}  │  ${NC}"

# --- Model ---
MODEL=$(echo "$input" | jq -r '.model.display_name // "Claude"')
MODEL_PART="${BOLD}${PURPLE}${MODEL}${NC}"

# --- Directory + git (cached per session_id) ---
DIR=$(echo "$input" | jq -r '.workspace.current_dir // "~"')
SESSION_ID=$(echo "$input" | jq -r '.session_id // "default"')
WORKTREE=$(echo "$input" | jq -r '.workspace.git_worktree // empty')
DIR_NAME=$(basename "$DIR")
DIR_PART="${ACCENT}${DIR_NAME}${NC}"

GIT_CACHE="/tmp/statusline-git-${SESSION_ID}"
GIT_CACHE_TTL=5

cache_stale() {
  [ ! -f "$GIT_CACHE" ] && return 0
  local age=$(( $(date +%s) - $(stat -f %m "$GIT_CACHE" 2>/dev/null || stat -c %Y "$GIT_CACHE" 2>/dev/null || echo 0) ))
  [ "$age" -gt "$GIT_CACHE_TTL" ]
}

GIT_PART=""
if git -C "$DIR" rev-parse --git-dir >/dev/null 2>&1; then
  if cache_stale; then
    BRANCH=$(git -C "$DIR" branch --show-current 2>/dev/null)
    STAGED=$(git -C "$DIR" diff --cached --numstat 2>/dev/null | wc -l | tr -d ' ')
    MODIFIED=$(git -C "$DIR" diff --numstat 2>/dev/null | wc -l | tr -d ' ')
    echo "${BRANCH}|${STAGED}|${MODIFIED}" > "$GIT_CACHE"
  else
    IFS='|' read -r BRANCH STAGED MODIFIED < "$GIT_CACHE"
  fi
  BRANCH_DISPLAY="${BRANCH}"
  [ "${#BRANCH}" -gt 40 ] && BRANCH_DISPLAY="${BRANCH:0:39}…"
  GIT_PART=" ${MUTED}on${NC} ${SUCCESS}${BRANCH_DISPLAY}${NC}"
  [ -n "$WORKTREE" ]  && GIT_PART="${GIT_PART} ${MUTED}(${WORKTREE})${NC}"
  [ "$STAGED"   -gt 0 ] && GIT_PART="${GIT_PART} ${SUCCESS}+${STAGED}${NC}"
  [ "$MODIFIED" -gt 0 ] && GIT_PART="${GIT_PART} ${WARN}~${MODIFIED}${NC}"
fi

# --- Context bar ---
CTX_SIZE=$(echo "$input"   | jq -r '.context_window.context_window_size // 200000')
IN_TOK=$(echo "$input"     | jq -r '.context_window.current_usage.input_tokens // 0')
CACHE_C=$(echo "$input"    | jq -r '.context_window.current_usage.cache_creation_input_tokens // 0')
CACHE_R=$(echo "$input"    | jq -r '.context_window.current_usage.cache_read_input_tokens // 0')
TOTAL=$(( IN_TOK + CACHE_C + CACHE_R ))

if [ "$CTX_SIZE" -gt 0 ] 2>/dev/null; then
  PCT=$(( TOTAL * 100 / CTX_SIZE ))
  [ "$PCT" -gt 100 ] && PCT=100
else
  PCT=0
fi

FILLED=$(( PCT * 8 / 100 )); EMPTY=$(( 8 - FILLED ))
printf -v FILL "%${FILLED}s"; printf -v PAD "%${EMPTY}s"
BAR_STR="${FILL// /=}${PAD// /.}"

if   [ "$PCT" -ge 80 ]; then BAR_COLOR="$ERROR"
elif [ "$PCT" -ge 50 ]; then BAR_COLOR="$WARN"
else                         BAR_COLOR="$SUCCESS"; fi

COST_RAW=$(echo "$input" | jq -r '.cost.total_cost_usd // empty')
COST_SUFFIX=""
if [ -n "$COST_RAW" ]; then
  COST_FMT=$(python3 -c "print(f'\${float(\"$COST_RAW\"):.2f}')" 2>/dev/null)
  COST_VAL=$(python3 -c "v=float(\"$COST_RAW\"); print(1 if v>=0.50 else (2 if v>=0.10 else 3))" 2>/dev/null)
  if   [ "$COST_VAL" = "1" ]; then COST_COLOR="$ERROR"
  elif [ "$COST_VAL" = "2" ]; then COST_COLOR="$WARN"
  else                              COST_COLOR="$SUCCESS"; fi
  COST_SUFFIX=" ${MUTED}(${NC}${COST_COLOR}${COST_FMT}${NC}${MUTED})${NC}"
fi

CTX_PART="${MUTED}ctx${NC} ${BAR_COLOR}[${BAR_STR}]${NC} ${MUTED}${PCT}%${NC}${COST_SUFFIX}"

# --- Rate limits with reset times ---
format_reset() {
  local ts="$1" fmt="$2"
  python3 -c "
import sys, datetime
try:
  dt = datetime.datetime.fromtimestamp(int(sys.argv[1])).astimezone()
  print(dt.strftime(sys.argv[2]))
except Exception:
  print('')
" "$ts" "$fmt" 2>/dev/null
}

rate_segment() {
  local label="$1" pct_raw="$2" reset_ts="$3" reset_fmt="$4"
  local pct color rst
  pct=$(printf '%.0f' "$pct_raw")
  if   [ "$pct" -ge 80 ]; then color="$ERROR"
  elif [ "$pct" -ge 50 ]; then color="$WARN"
  else                         color="$SUCCESS"; fi
  local seg="${MUTED}${label}${NC} ${color}${pct}%${NC}"
  if [ -n "$reset_ts" ]; then
    rst=$(format_reset "$reset_ts" "$reset_fmt")
    [ -n "$rst" ] && seg+=" ${MUTED}rst${NC} ${PRIMARY}${rst}${NC}"
  fi
  echo "$seg"
}

RATE_PARTS=""
FIVE_PCT=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
FIVE_TS=$(echo "$input"  | jq -r '.rate_limits.five_hour.resets_at // empty')
WEEK_PCT=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')
WEEK_TS=$(echo "$input"  | jq -r '.rate_limits.seven_day.resets_at // empty')

[ -n "$FIVE_PCT" ] && RATE_PARTS="$(rate_segment '5h' "$FIVE_PCT" "$FIVE_TS" '%H:%M')"
if [ -n "$WEEK_PCT" ]; then
  WEEK_SEG="$(rate_segment '7d' "$WEEK_PCT" "$WEEK_TS" '%a %d %H:%M')"
  [ -n "$RATE_PARTS" ] && RATE_PARTS+="${SEP}${WEEK_SEG}" || RATE_PARTS="$WEEK_SEG"
fi

# --- Assemble ---
LINE="${MODEL_PART}${SEP}${DIR_PART}${GIT_PART}${SEP}${CTX_PART}"
[ -n "$RATE_PARTS" ] && LINE+="${SEP}${RATE_PARTS}"

echo -e "${LINE}\033[K"
