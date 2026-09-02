#!/bin/sh
# ─────────────────────────────────────────────────────────────────────────────
# pre-commit — secret scanner
#
# THE GITHUB REPO IS PUBLIC. This hook refuses any commit whose STAGED ADDED
# LINES contain a credential, a real identity, or a private host.
#
# It lives in .git/hooks/ and is NEVER pushed — it is a local guard only.
#
# Bypass (only when you are certain it is a false positive):
#     git commit --no-verify
#
# Real values belong in backend/.env (gitignored). Tracked files reference the
# env var NAME, never its value. Placeholders must be obviously fake:
#     +911234567890   +1XXXXXXXXXX   <static-domain>   <YOUR_TOKEN>   AC…
# ─────────────────────────────────────────────────────────────────────────────

FAIL=0

# Added lines only. Deletions and context lines are irrelevant — we care about
# what is entering the repo, not what is leaving it.
#
# *.example / *.sample templates hold only placeholders by definition and are
# meant to be committed — they legitimately contain env-var-shaped and
# host-shaped placeholders. Exempt them from scanning (standard practice: e.g.
# gitleaks allowlists example files). Real .env* files are still scanned below.
SCAN_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -vE '\.(example|sample)$')

if [ -z "$SCAN_FILES" ]; then
  ADDED=""
else
  ADDED=$(git diff --cached -U0 -- $SCAN_FILES | grep '^+' | grep -v '^+++')
fi

[ -z "$ADDED" ] && exit 0

# Lines that are explicitly documented placeholders are exempt from the phone
# and host checks. Without this, our own examples would block every commit.
SAFE=$(printf '%s\n' "$ADDED" \
  | grep -v 'XXXXXXX' \
  | grep -v '911234567890' \
  | grep -v '919876543210' \
  | grep -v '1234567890' \
  | grep -v '15551234567' \
  | grep -v '<static-domain>' \
  | grep -v 'your-tunnel-domain' \
  | grep -v 'example\.com')

report() {
  echo ""
  echo "  ✖ $1"
  printf '%s\n' "$2" | head -4 | sed 's/^/      /'
  FAIL=1
}

check() {
  hits=$(printf '%s\n' "$3" | grep -Ei "$2")
  [ -n "$hits" ] && report "$1" "$hits"
}

# ── Credentials ──────────────────────────────────────────────────────────────
check "Telegram bot token"      '[0-9]{8,10}:[A-Za-z0-9_-]{35}'            "$ADDED"
check "Twilio Account SID"      'AC[0-9a-f]{32}'                           "$ADDED"
check "OpenAI / Groq style key" '(sk-[A-Za-z0-9]{20,}|gsk_[A-Za-z0-9]{20,})' "$ADDED"
check "GitHub token"            'gh[pousr]_[A-Za-z0-9]{30,}'               "$ADDED"
check "Slack token"             'xox[baprs]-[A-Za-z0-9-]{10,}'             "$ADDED"
check "AWS access key"          'AKIA[0-9A-Z]{16}'                         "$ADDED"
check "Private key block"       'BEGIN [A-Z ]*PRIVATE KEY'                 "$ADDED"

# A secret assigned inline rather than read from the environment.
check "Hardcoded secret assignment" \
  '(TOKEN|SECRET|PASSWORD|API_KEY|AUTH_TOKEN)[A-Z_]*[[:space:]]*[=:][[:space:]]*["'"'"'][A-Za-z0-9_/+-]{16,}' \
  "$ADDED"

# ── Identities ───────────────────────────────────────────────────────────────
check "Real phone number"       '\+[1-9][0-9]{9,14}'                       "$SAFE"
check "Personal email address"  '[A-Za-z0-9._%+-]+@(gmail|zohomail|outlook|yahoo|hotmail|protonmail)\.'  "$SAFE"

# ── Private hosts ────────────────────────────────────────────────────────────
check "Tunnel domain"           '[a-z0-9-]+\.(ngrok(-free)?\.(dev|app|io)|loca\.lt|trycloudflare\.com)'  "$SAFE"
check "Supabase host"           '[a-z0-9.-]*supabase\.(co|com)'            "$SAFE"
check "Render host"             '[a-z0-9-]+\.onrender\.com'                "$SAFE"

# ── Env files ────────────────────────────────────────────────────────────────
if git diff --cached --name-only | grep -vE '\.(example|sample)$' | grep -Eq '(^|/)\.env($|\.)' ; then
  report "A .env file is staged" "$(git diff --cached --name-only | grep -vE '\.(example|sample)$' | grep -E '(^|/)\.env($|\.)')"
fi

if [ "$FAIL" -ne 0 ]; then
  echo ""
  echo "  ────────────────────────────────────────────────────────────────"
  echo "  COMMIT BLOCKED — the staged changes contain a secret or identity."
  echo ""
  echo "  Fix: move the real value into backend/.env and reference the env"
  echo "  var name instead, or replace it with an obviously fake placeholder."
  echo ""
  echo "  Genuine false positive?  git commit --no-verify"
  echo "  ────────────────────────────────────────────────────────────────"
  echo ""
  exit 1
fi

exit 0
