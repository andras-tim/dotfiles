#!/bin/bash -e
# Source: https://wiki.archlinux.org/index.php/Tmux#Shift.2BF6_not_working_in_Midnight_Commander
SETTNGS='kf16=\E[29~'

function is_required()
{
    set +e
    infocmp | grep -Fq "${SETTNGS}" && return 1
    return 0
}

function get_patched_config()
{
    infocmp
    echo '  kf16=\E[29~,'
}

function patch_config()
{
    tmp=$(tempfile)
    get_patched_config > "${tmp}"
    tic "${tmp}"
    rm "${tmp}"
}

if is_required
then
    patch_config
    echo "$TERM patch done!"
fi
