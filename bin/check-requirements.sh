#!/bin/bash
REQUIREMENTS='urxvt xsel tmux'

function check()
{
    local tool="$1"

    "$1" --help &>/dev/null
    if [ $? -eq 127 ]
    then
        echo "${tool}"
    fi
}

function get_missing_requirements()
{
    for command in $REQUIREMENTS
    do
        check "${command}"
    done
}

function err()
{
    echo -en "$1" >&2
}


# Main
missing_requirements="$(get_missing_requirements)"
if [ "${missing_requirements}" != '' ]
then
    err "Missing requirements:"
    echo "${missing_requirements}" | while read command
    do
        err " ${command}"
    done
    err "\n"
    exit 1
fi
exit 0
