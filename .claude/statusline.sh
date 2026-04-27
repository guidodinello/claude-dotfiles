#!/bin/bash
input=$(cat)

MODEL=$(echo "$input" | jq -r '.model.display_name')
DIR=$(echo "$input"   | jq -r '.workspace.current_dir')
COST=$(echo "$input"  | jq -r '.cost.total_cost_usd // 0')
PCT=$(echo "$input"   | jq -r '.context_window.used_percentage // empty' | cut -d. -f1)
DUR=$(echo "$input"   | jq -r '.cost.total_duration_ms // 0')
# shellcheck disable=SC2034
WIN_SIZE=$(echo "$input" | jq -r '.context_window.context_window_size // 200000')
# shellcheck disable=SC2034
IN_TOKENS=$(echo "$input" | jq -r '.context_window.total_input_tokens // empty')

CYAN='\033[36m'; GREEN='\033[32m'; YELLOW='\033[33m'; RED='\033[31m'; RESET='\033[0m'

# --- Line 1: model, dir, git ---
GIT_PART=""
if git -C "$DIR" rev-parse --git-dir > /dev/null 2>&1; then
    BRANCH=$(git -C "$DIR" branch --show-current 2>/dev/null)
    STAGED=$(git -C "$DIR" diff --cached --numstat 2>/dev/null | wc -l | tr -d ' ')
    MODIFIED=$(git -C "$DIR" diff --numstat 2>/dev/null | wc -l | tr -d ' ')
    GIT_PART=" ${GREEN}${BRANCH}${RESET}"
    [ "$STAGED"   -gt 0 ] && GIT_PART="${GIT_PART} ${GREEN}+${STAGED}${RESET}"
    [ "$MODIFIED" -gt 0 ] && GIT_PART="${GIT_PART} ${YELLOW}~${MODIFIED}${RESET}"
fi
echo -e "${CYAN}[${MODEL}]${RESET} ${DIR##*/}${GIT_PART}"

# --- Line 2: context bar, cost, duration ---
if [ -z "$PCT" ] || [ -z "$IN_TOKENS" ]; then
    BAR_COLOR="$GREEN"
    FILLED=0; EMPTY=10
    CTX_LABEL="--/$(( WIN_SIZE / 1000 ))k"
else
    if   [ "$PCT" -ge 90 ]; then BAR_COLOR="$RED"
    elif [ "$PCT" -ge 70 ]; then BAR_COLOR="$YELLOW"
    else                         BAR_COLOR="$GREEN"; fi
    FILLED=$((PCT / 10)); EMPTY=$((10 - FILLED))
    USED_K=$(( (IN_TOKENS + 500) / 1000 ))
    WIN_K=$(( WIN_SIZE / 1000 ))
    CTX_LABEL="${USED_K}k/${WIN_K}k (${PCT}%)"
fi

printf -v FILL "%${FILLED}s" 2>/dev/null; printf -v PAD "%${EMPTY}s" 2>/dev/null
BAR="${FILL// /█}${PAD// /░}"

MINS=$((DUR / 60000)); SECS=$(( (DUR % 60000) / 1000 ))
COST_FMT=$(printf '$%.3f' "$COST")

echo -e "${BAR_COLOR}${BAR}${RESET} ${CTX_LABEL} | ${YELLOW}${COST_FMT}${RESET} | ⏱  ${MINS}m ${SECS}s"
