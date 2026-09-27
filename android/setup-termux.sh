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

    # Pinned at 2.1.112 — newer versions ship a native claude binary that is non-PIE (ET_EXEC),
    # which Android rejects. The @anthropic-ai/claude-code-linux-arm64-android npm package was
    # never published, and the linux-arm64 binary also fails. Bump only when Anthropic publishes
    # a proper PIE/android build. Side-effect: `claude rc` (Remote Control) requires a newer version.
    npm install -g @anthropic-ai/claude-code@2.1.112 --ignore-scripts
    # 2.1.112 bundles ripgrep per-platform but omits arm64-android; symlink Termux's PIE build
    local rg_dir
    rg_dir="$(npm root -g)/@anthropic-ai/claude-code/vendor/ripgrep/arm64-android"
    mkdir -p "$rg_dir"
    ln -sf "$(command -v rg)" "$rg_dir/rg"

    cargo install --locked git-igitt
}

function install_opentofu() {
    # No Termux package exists; the official linux_arm64 build is a static Go binary.
    # Same version as the infra repo's app.install `opentofu` profile. Providers are not mirrored here:
    # tofu fetches them from the registry at the versions pinned in each root's .terraform.lock.hcl.
    local version='1.12.6'
    local sha256='e573979ba68a17fe7b881752051a694a7efcd970e39521f6a25775197861ed4d'
    local zip="${TMPDIR}/tofu_${version}_linux_arm64.zip"

    pkg install -y curl unzip
    curl -fL -o "${zip}" "https://github.com/opentofu/opentofu/releases/download/v${version}/tofu_${version}_linux_arm64.zip"
    echo "${sha256}  ${zip}" | sha256sum -c -
    unzip -o -d "${TMPDIR}" "${zip}" tofu
    install -m 755 "${TMPDIR}/tofu" "${PREFIX}/bin/tofu"
    rm -f "${zip}" "${TMPDIR}/tofu"
    tofu version
}

function _inject_myrc_line() {
    local header="$1"
    local cmd="$2"

    if [ -e ~/.myrc_host ]; then
        sed -i "/${header}/,+1d" ~/.myrc_host
    fi
    echo -e "\n${header}\n${cmd}" >> ~/.myrc_host
}

function inject_myrc_lines() {
    echo -en "\nInjecting ~/.myrc_host lines... " >&2
    _inject_myrc_line '### auto-exec-tmux ###' '[ -n "${TMUX:-}" ] || exec tmux'
    _inject_myrc_line '### warn-if-no-ssh-agent ###' \
        'ssh-add -l >/dev/null 2>&1 || echo "SSH agent not running — run: ssh-load-key" >&2'
    # Bionic getpwnam returns pw_dir='/data' for Termux app UIDs, breaking Ansible's
    # ~<user> synthesis; the literal ${HOME} is expanded by the target shell.
    _inject_myrc_line '### ansible-remote-tmp ###' \
        "export ANSIBLE_REMOTE_TEMP='\${HOME}/.ansible/tmp'"
    echo 'Done' >&2
}

function setup_user_env() {
    chsh -s zsh
    "${BASE_DIR}/../install" termux

    inject_myrc_lines
}

function main() {
    precheck
    preinit

    install_runtimes
    install_build_toolchain
    install_tools
    install_opentofu

    setup_user_env
}


if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
