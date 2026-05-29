#!/bin/bash
set -eufo pipefail

BASE_DIR="$(dirname -- "${BASH_SOURCE[0]}")"


function precheck() {
    if ! [[ $SHELL =~ /com\.termux/ ]]; then
        echo Abort! It must run within termux environment >&2
        exit 1
    fi
}

function _is_x11_apk_installed() {
    cmd package list packages --user 0 -e -f 2>/dev/null | grep -q "com.termux.x11" && return
    pm list packages -e 2>/dev/null | grep -q "com.termux.x11"
}

function install_x11() {
    if ! _is_x11_apk_installed; then
        echo "ERROR: Termux:X11 APK is not installed on the Android side." >&2
        echo "  NOTE: Disable 'Auto Blocker' in Samsung Settings → Security before installing." >&2
        echo "  https://github.com/termux/termux-x11/releases/download/nightly/app-arm64-v8a-debug.apk" >&2
        exit 1
    fi

    pkg install -y x11-repo
    pkg install -y \
        aspell \
        aspell-en \
        openbox \
        st \
        termux-am \
        termux-x11-nightly \
        tk \
        xsel
}

function setup_user_env() {
    "${BASE_DIR}/../install" desktop
}

function main() {
    precheck

    install_x11

    setup_user_env
}


if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
