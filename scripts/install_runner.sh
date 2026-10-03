#!/usr/bin/env bash
# Install this repo as a self-hosted GitHub Actions runner.
#
# Run it ON the machine that will execute the bot (a Linux box/VM on a
# residential connection — see AGENTS.md for why that matters).
#
#   bash scripts/install_runner.sh <owner>/<repo> [runner-name] [labels]
#
# Defaults: name = hostname, labels = "self-hosted,linux,ig-bot"
# Requires: curl, tar, and either `gh` (logged in) or a registration token in
# $RUNNER_TOKEN. Installs into ~/actions-runner and registers a systemd service
# (needs sudo for `svc.sh install`; without sudo it prints the manual command).
set -euo pipefail

REPO="${1:?usage: install_runner.sh <owner>/<repo> [runner-name] [labels]}"
NAME="${2:-$(hostname)-ig-bot}"
LABELS="${3:-self-hosted,linux,ig-bot}"
DIR="$HOME/actions-runner"

echo "==> repo=$REPO name=$NAME labels=$LABELS dir=$DIR"
mkdir -p "$DIR" && cd "$DIR"

if [ ! -f ./config.sh ]; then
  echo "==> downloading the latest runner"
  VER=$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest \
        | grep -oP '"tag_name":\s*"v\K[^"]+')
  TARBALL="actions-runner-linux-x64-${VER}.tar.gz"
  curl -fsSL -o "$TARBALL" \
    "https://github.com/actions/runner/releases/download/v${VER}/${TARBALL}"
  tar xzf "$TARBALL"
  rm -f "$TARBALL"
fi

if [ -z "${RUNNER_TOKEN:-}" ]; then
  command -v gh >/dev/null || { echo "need gh or RUNNER_TOKEN"; exit 1; }
  echo "==> fetching a registration token"
  RUNNER_TOKEN=$(gh api -X POST "repos/${REPO}/actions/runners/registration-token" --jq .token)
fi

if [ ! -f .runner ]; then
  echo "==> configuring"
  ./config.sh --url "https://github.com/${REPO}" --token "$RUNNER_TOKEN" \
    --name "$NAME" --labels "$LABELS" --unattended --replace
fi

if [ "${SKIP_SERVICE:-0}" = "1" ]; then
  echo "==> SKIP_SERVICE=1: start it manually with:  cd $DIR && ./run.sh"
  exit 0
fi

if sudo -n true 2>/dev/null; then
  sudo ./svc.sh install "$USER"
  sudo ./svc.sh start
  sudo ./svc.sh status || true
else
  echo "==> no passwordless sudo — start the runner manually (or run as a user service):"
  echo "      cd $DIR && ./run.sh          # foreground"
  echo "      nohup ./run.sh >runner.log 2>&1 &   # background"
fi

cat <<'EOF'

==> done. Next steps:
  1. gh variable set CI_RUNNER --body "self-hosted" -R <owner>/<repo>
     (workflows then run on this machine instead of ubuntu-latest)
  2. This machine needs a browser signed in to gemini.google.com (Firefox) for
     automatic Gemini-cookie refresh — see AGENTS.md.
  3. Verify: Actions → "CI probe" → Run workflow, then read the verdicts.
EOF
