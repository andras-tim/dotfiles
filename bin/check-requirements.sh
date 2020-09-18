#!/bin/bash

function main()
{
    missing_requirements="$(get_missing_requirements "$@")"
    if [ "${missing_requirements}" != '' ]
    then
        err "Missing requirements:"
        echo "${missing_requirements}" | while read -r command
        do
            err " ${command}"
        done
        err "\n"
        exit 1
    fi
}

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
    for command in "$@"
    do
        check "${command}"
    done
}

function err()
{
    echo -en "$1" >&2
}


main "$@"
