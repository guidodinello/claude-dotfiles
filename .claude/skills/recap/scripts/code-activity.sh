#!/usr/bin/env bash
# Usage: code-activity.sh FROM [TO] [ROOT]
#   FROM/TO  YYYY-MM-DD, inclusive, interpreted in the machine's local timezone.
#   ROOT     directory to resolve repos from (default: $PWD). A lightit-ai.json
#            manifest found walking up from ROOT supplies the repos; otherwise
#            the git repo containing ROOT is used.
# Prints one JSON object: window, PRs opened/closed and reviews submitted in it,
# local commits, and every PR of mine still open now.
set -euo pipefail

from=${1:?FROM date required (YYYY-MM-DD)}
to=${2:-$from}
root=${3:-$PWD}

tz=$(date +%z)
offset="${tz:0:3}:${tz:3:2}"
start="${from}T00:00:00${offset}"
end="${to}T23:59:59${offset}"
start_epoch=$(date -j -f "%Y-%m-%dT%H:%M:%S%z" "${from}T00:00:00${tz}" +%s)
end_epoch=$(date -j -f "%Y-%m-%dT%H:%M:%S%z" "${to}T23:59:59${tz}" +%s)

owner_of() {
    local url=${1%.git}
    url=${url%/*}
    echo "${url##*[:/]}"
}

repo_paths=()
owners=()
dir=$(cd "$root" && pwd)
manifest=""
while [ "$dir" != "/" ]; do
    if [ -f "$dir/lightit-ai.json" ]; then manifest="$dir/lightit-ai.json"; break; fi
    dir=$(dirname "$dir")
done

if [ -n "$manifest" ]; then
    base=$(dirname "$manifest")
    while IFS=$'\t' read -r path url; do
        [ -d "$base/$path/.git" ] || [ -f "$base/$path/.git" ] || continue
        repo_paths+=("$base/$path")
        owners+=("$(owner_of "$url")")
    done < <(jq -r '.repos[] | [.path, .url] | @tsv' "$manifest")
else
    top=$(git -C "$root" rev-parse --show-toplevel)
    repo_paths+=("$top")
    owners+=("$(owner_of "$(git -C "$top" remote get-url origin)")")
fi

owners_json=$(printf '%s\n' "${owners[@]}" | sort -u | jq -R . | jq -s .)
me=$(gh api user -q .login)

authored='[]'
reviewed='[]'
open_prs='[]'
for owner in $(echo "$owners_json" | jq -r '.[]'); do
    batch=$(gh search prs --author=@me --owner="$owner" --updated=">=${start}" --created="<=${end}" \
        --json number,title,url,state,isDraft,createdAt,closedAt,repository --limit 300)
    authored=$(jq -s 'add' <(echo "$authored") <(echo "$batch"))

    open_batch=$(gh search prs --author=@me --owner="$owner" --state=open \
        --json number,title,url,isDraft,repository --limit 100 \
        | jq 'map({repo: .repository.nameWithOwner, number, title, url, isDraft})')
    open_prs=$(jq -s 'add' <(echo "$open_prs") <(echo "$open_batch"))

    candidates=$(gh search prs --reviewed-by=@me --owner="$owner" --updated=">=${start}" --created="<=${end}" \
        --json number,title,url,repository,author --limit 300 \
        | jq --arg me "$me" 'map(select(.author.login != $me))')
    while IFS=$'\t' read -r repo number title url; do
        [ -n "$repo" ] || continue
        mine=$(gh api "repos/$repo/pulls/$number/reviews" --paginate \
            --jq "[.[] | select(.user.login == \"$me\" and .submitted_at != null)
                   | select((.submitted_at | fromdateiso8601) >= $start_epoch
                        and (.submitted_at | fromdateiso8601) <= $end_epoch)
                   | {state, submitted_at}]" | jq -s 'add // []')
        if [ "$(echo "$mine" | jq 'length')" -gt 0 ]; then
            reviewed=$(jq -n --argjson acc "$reviewed" --argjson r "$mine" \
                --arg repo "$repo" --argjson number "$number" --arg title "$title" --arg url "$url" \
                '$acc + [{repo: $repo, number: $number, title: $title, url: $url, reviews: $r}]')
        fi
    done < <(echo "$candidates" | jq -r '.[] | [.repository.nameWithOwner, .number, .title, .url] | @tsv')
done

authored=$(echo "$authored" | jq --argjson s "$start_epoch" --argjson e "$end_epoch" '
    map({
        repo: .repository.nameWithOwner, number, title, url, state, isDraft,
        opened_in_window: ((.createdAt | fromdateiso8601) as $t | $t >= $s and $t <= $e),
        closed_in_window: (.closedAt != null and (.closedAt | startswith("0001") | not)
            and ((.closedAt | fromdateiso8601) as $t | $t >= $s and $t <= $e))
    })
    | map(select(.opened_in_window or .closed_in_window))')

commits='[]'
for path in "${repo_paths[@]}"; do
    email=$(git -C "$path" config user.email)
    batch=$(git -C "$path" log --all --no-merges --author="$email" \
            --since="$start" --until="$end" --format='%h%x09%aI%x09%s' \
        | jq -R --arg repo "$(basename "$path")" \
            'split("\t") | {repo: $repo, sha: .[0], at: .[1], subject: .[2]}' \
        | jq -s .)
    commits=$(jq -s 'add' <(echo "$commits") <(echo "$batch"))
done

jq -n --arg start "$start" --arg end "$end" --arg me "$me" \
    --argjson authored "$authored" --argjson reviewed "$reviewed" --argjson commits "$commits" \
    --argjson open "$open_prs" \
    '{window: {start: $start, end: $end}, github_login: $me,
      authored_prs: $authored, reviewed_prs: $reviewed, local_commits: $commits,
      open_prs_now: $open}'
