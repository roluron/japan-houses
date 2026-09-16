#!/bin/bash
# Daily run on the Mac mini (launchd → com.fromanother.japan-houses).
# Scans athome, commits ledger.json + diff.md, pushes to GitHub.
set -u
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/Library/Python/3.9/bin:$PATH"
REPO="$HOME/japan-houses"
LOG="$HOME/Library/Logs/japan-houses.log"
cd "$REPO" || exit 1
{
  echo "=== $(date '+%F %T %Z') start"
  git pull --rebase --quiet origin main || echo "git pull failed (continuing)"
  python3 scan.py
  git add ledger.json diff.md history/
  if git diff --cached --quiet; then
    echo "nothing to commit"
  else
    git commit -q -m "scan $(TZ=Asia/Tokyo date +%F)" && git push -q origin main && echo "pushed"
  fi
  echo "=== $(date '+%F %T %Z') end"
} >> "$LOG" 2>&1
