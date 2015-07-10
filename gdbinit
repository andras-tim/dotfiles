#set confirm off
set verbose off
set output-radix 10
set input-radix 10

# Colored prompt
#set prompt \033[31mgdb$ \033[0m

# These make gdb never pause in its output
#set height 0
#set width 0

# Pretty print
set print pretty on
set print object on
set print static-members on
set print vtbl on
set print demangle on
set demangle-style gnu-v3
set print sevenbit-strings off
