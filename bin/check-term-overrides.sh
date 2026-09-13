#!/bin/bash
set -eufo pipefail

TERM_OVERRIDES_DIR="${HOME}/.terminfo"

if [ -e "${TERM_OVERRIDES_DIR}" ]; then
    echo \
        "WARNING: You have '${TERM_OVERRIDES_DIR}' directory." \
        "If you have custom overrides your terminal and tmux can work badly!" \
        >&2
    exit 1
fi

exit 0
