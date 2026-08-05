# load-ssh-key.sh
# SOURCE this file, do not execute it:
#   source load-ssh-key.sh   (or: . load-ssh-key.sh)

# refuse to run if executed rather than sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "This file must be sourced, not executed:" >&2
  echo "  source ${BASH_SOURCE[0]}" >&2
  exit 1
fi

# start an agent only if one isn't already running in this shell
if [[ -z "${SSH_AUTH_SOCK:-}" ]]; then
  eval "$(ssh-agent -s)" >/dev/null
fi

# fetch the key; bail out cleanly if the fetch fails (return, not exit)
if ! key="$(gcloud secrets versions access latest \
    --project=mf-crucible --secret=crucible-print-ssh-key)"; then
  echo "secret fetch failed" >&2
  return 1
fi

# load into the agent from stdin — never touches disk — with a 1h lifetime
ssh-add -t 3600 - <<<"$key"
unset key