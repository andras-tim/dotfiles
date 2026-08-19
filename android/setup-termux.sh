#!/bin/bash
set -eufo pipefail

BASE_DIR="$(dirname -- "${BASH_SOURCE[0]}")"


function precheck() {
    if ! [[ $SHELL =~ /com\.termux/ ]]; then
        echo Abort! It must run within termux environment >&2
        exit 1
    fi
}

function preinit() {
    if ! [ -e "${HOME}/storage" ]; then
        termux-setup-storage
    fi

    termux-setup-package-manager

    pkg upgrade -y
    apt autoremove -y
    pkg autoclean -y
}

function install_runtimes() {
    # Runtimes & they useful common libs
    pkg install -y \
        libyaml \
        nodejs \
        python \
        python-cryptography \
        python-lxml
}

function install_build_toolchain() {
    # Required for pip source builds
    pkg install -y \
        build-essential \
        rust
        #autoconf \
        #automake \
        #binutils \
        #clang \
        #libtool \
        #make \
        #pkg-config \
}

function install_tools() {
    # Shell & tools
    pkg install -y \
        curl \
        gh \
        git \
        git-lfs \
        gitui \
        htop \
        mc \
        openssh \
        ripgrep \
        rsync \
        tig \
        tmux \
        vim \
        wget \
        zsh

    # Pinned: newer releases dropped linux-arm64-android support entirely
    npm install -g @anthropic-ai/claude-code@2.1.112 --ignore-scripts
    # 2.1.112 ships no arm64-android ripgrep binary; symlink Termux's PIE build
    local rg_dir
    rg_dir="$(npm root -g)/@anthropic-ai/claude-code/vendor/ripgrep/arm64-android"
    mkdir -p "$rg_dir"
    ln -sf "$(command -v rg)" "$rg_dir/rg"

    cargo install --locked git-igitt
}

function _inject_tmux_as_default_app() {
    local header='### auto-exec-tmux ###'
    local cmd='[ -n "${TMUX:-}" ] || exec tmux'

    if [ -e ~/.myrc_host ]; then
        sed -i "/${header}/,+1d" ~/.myrc_host
    fi
    echo -e "\n${header}\n${cmd}" >> ~/.myrc_host
}

function setup_user_env() {
    chsh -s zsh
    "${BASE_DIR}/../install" termux

    echo -en "\nInjecting tmux as termux startup app... " >&2
    _inject_tmux_as_default_app
    echo 'Done' >&2
}

function main() {
    precheck
    preinit

    install_runtimes
    install_build_toolchain
    install_tools

    setup_user_env
}


if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
