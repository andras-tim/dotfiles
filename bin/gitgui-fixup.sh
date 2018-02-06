#!/bin/bash
set -eufo pipefail

COMMAND=(git commit --fixup)


function get_commit_id()
{
    zenity --entry --title "$*" --window-icon question --text 'Commit ID:' 2>/dev/null || true
}


commit_id="$(get_commit_id)"
if [ "${commit_id}" == '' ]
then
    echo 'Aborted'
    exit 1
fi

set -x
"${COMMAND[@]}" "${commit_id}"
