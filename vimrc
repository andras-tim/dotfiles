"""Others"""
set title
set showmode
set ttyfast

set wildchar=<TAB>
set softtabstop=4
set shiftwidth=4
set tabstop=4

set smartindent
set paste

set ignorecase
set hlsearch
set incsearch
set showmatch
set expandtab


"""Show Position"""
set numberwidth=3
"set number
set ruler


"""Tmux fixes/workarounds"""
set term=xterm-256color


"""Highlight"""
colo default
set background=dark

highlight LineNr term=bold cterm=NONE ctermfg=DarkGrey ctermbg=NONE gui=NONE guifg=DarkGrey guibg=NONE
highlight WhitespaceEOL term=reverse ctermbg=Red guibg=Red
match WhitespaceEOL /\s\+$/

highlight SpecialKey ctermfg=Black ctermbg=Yellow guibg=Yellow
set list
set listchars=tab:>-

set colorcolumn=120


"""File types"""
syntax on
filetype plugin on


"""Shortcuts"""
nnoremap <F5> :! clear; PROMPT_EXTRA='[VIM]' /bin/bash<CR><CR>
nnoremap <f12> :set filetype=python<cr>


"""Trailing whitespaces"""
autocmd bufwritepre * let save_cursor = getpos( '.' ) |
                    \ silent %s/[ \t]\+$//ge          |
                    \ silent %s/\n*\%$//e             |
                    \ call setpos( '.', save_cursor )
