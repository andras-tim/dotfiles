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

    cargo install --locked git-igitt
}

function install_claude_code() {
    # Newer @anthropic-ai/claude-code ships a glibc linux-arm64 native binary and no
    # arm64-android target, so we run it from inside a proot-distro ubuntu rootfs
    # via a thin wrapper. Termux $HOME is auto-bound at the same path inside the
    # container — sibling to that, we scrub PATH so Termux's own node/npm/bash
    # cannot shadow the ubuntu ones through the bind.
    pkg install -y proot-distro

    npm uninstall -g @anthropic-ai/claude-code >/dev/null 2>&1 || true
    rm -f "${PREFIX}/bin/claude"

    if [ ! -d "${PREFIX}/var/lib/proot-distro/containers/ubuntu" ]; then
        proot-distro install ubuntu
    fi

    proot-distro login ubuntu --shared-tmp -- env -i \
        HOME=/root \
        PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
        TERM="${TERM:-xterm-256color}" \
        DEBIAN_FRONTEND=noninteractive \
        bash -eu <<'SETUP'
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl gnupg
if ! command -v node >/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_lts.x | bash -
    apt-get install -y nodejs
fi
npm install -g --allow-scripts=@anthropic-ai/claude-code @anthropic-ai/claude-code
SETUP

    install -m 755 /dev/stdin "${PREFIX}/bin/claude" <<'WRAP'
#!/bin/bash
# Scrub Termux PATH so the wrapper doesn't re-resolve `claude` to itself inside
# the container (Termux $HOME/$PREFIX is auto-bound → /data/.../usr/bin is visible).
exec proot-distro login ubuntu --shared-tmp -- env -i \
    HOME=/root \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    TERM="${TERM:-xterm-256color}" \
    LANG="${LANG:-C.UTF-8}" \
    ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
    SSH_AUTH_SOCK="${SSH_AUTH_SOCK:-}" \
    USER_PWD="$(pwd)" \
    bash -lc 'cd "$USER_PWD" 2>/dev/null; exec claude "$@"' -- "$@"
WRAP
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

function cleanup_opentofu() {
    # TODO: temporary, until a working setup (e.g. proot-distro) replaces install_opentofu.
    # The linux_arm64 build is static non-PIE (ELF e_type 2) and Android's linker refuses it ("unexpected e_type: 2");
    # remove the unusable binary an earlier install_opentofu left behind. A tofu that runs is kept.
    if [ -e "${PREFIX}/bin/tofu" ] && ! "${PREFIX}/bin/tofu" version >/dev/null 2>&1; then
        echo "Removing unusable ${PREFIX}/bin/tofu" >&2
        rm -f "${PREFIX}/bin/tofu"
    fi
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
    install_claude_code
    # install_opentofu  # TODO: disabled, the binary does not run on Android (see cleanup_opentofu)
    cleanup_opentofu

    setup_user_env
}


if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
