#!/usr/bin/env bash
set -euo pipefail

# Pulls SSH key from google secrets and activates 
# in terminal with ssh-agent

# start an ssh agent if one isn't already running
if [[ -z "${SSH_AUTH_SOCK:-}" ]]; then
  eval "$(ssh-agent -s)" >/dev/null
  trap 'ssh-agent -k >/dev/null' EXIT
fi

# pull key from google secrets straight into the agent — never touches disk
gcloud secrets versions access latest --project=mf-crucible --secret=crucible-print-ssh-key  \
  | ssh-add - 
