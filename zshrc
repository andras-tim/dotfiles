# Path to your oh-my-zsh configuration.
export ZSH=${HOME}/.oh-my-zsh

# Set name of the theme to load.
# Look in ${HOME}/.oh-my-zsh/themes/
# Optionally, if you set this to "random", it'll load a random theme each
# time that oh-my-zsh is loaded.
export ZSH_THEME=bash

# Set to this to use case-sensitive completion
export CASE_SENSITIVE="true"

# Comment this out to disable weekly auto-update checks
export DISABLE_AUTO_UPDATE="true"

# Uncomment following line if you want to disable colors in ls
# export DISABLE_LS_COLORS="true"

# Uncomment following line if you want to disable autosetting terminal title.
# export DISABLE_AUTO_TITLE="true"

# Which plugins would you like to load? (plugins can be found in ${HOME}/.oh-my-zsh/plugins/*)
# Example format: plugins=(rails git textmate ruby lighthouse)
plugins=(git-flow compleat command-not-found zsh-syntax-highlighting)

source $ZSH/oh-my-zsh.sh

# Customize to your needs...
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:${HOME}/bin

bindkey '3C' forward-word
bindkey '3D' backward-word
bindkey '5C' forward-word
bindkey '5D' backward-word

# Config
unsetopt auto_menu
unsetopt correct_all
unsetopt bang_hist
setopt check_jobs
setopt interactive_comments
setopt notify

# Import myrc
source ${HOME}/.myrc

export HISTSIZE=100000
export SAVEHIST=100000

export PERL_LOCAL_LIB_ROOT="${HOME}/perl5";
export PERL_MB_OPT="--install_base ${HOME}/perl5";
export PERL_MM_OPT="INSTALL_BASE=${HOME}/perl5";
export PERL5LIB="${HOME}/perl5/lib/perl5/x86_64-linux-gnu-thread-multi:${HOME}/perl5/lib/perl5";
export PATH="${HOME}/perl5/bin:$PATH";
