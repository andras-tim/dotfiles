conky.config={
-- set to = true if you want Conky to be forked in the background
background = false,
cpu_avg_samples = 2,
net_avg_samples = 2,
out_to_console = false,
--out_to_stderr = false,

-- Use Xft?
use_xft = true,
font = "Andale Mono:size=7",
--xftalpha = 0.6,
--on_bottom = false,

-- Update interval in seconds
update_interval = 2,

-- Exec
text_buffer_size = 1024,

-- Create own window instead of using desktop (required in nautilus)
own_window = true,
own_window_transparent = false,
own_window_class = "Conky",
own_window_type = "override",

-- Use double buffering (reduces flicker, may not work for everyone)
double_buffer = true,

-- Minimum size of text area
maximum_width = 260,
minimum_width = 200,
minimum_height = 5,

-- Draw shades?
draw_shades = false,

-- Draw outlines?
draw_outline = false,

-- Draw borders around text
draw_borders = false,

-- Stippled borders?
stippled_borders = 0,

-- border margins
-- border_margin = 10,

-- border width
border_width = 5,

-- Default colors and also border colors
default_color = "white",
default_shade_color = "white",
default_outline_color = "white",

-- Text alignment, other possible values are commented
gap_x = 15,
gap_y = 40,
alignment = "top_right",

-- Defaults for execXXX calls
default_bar_width = 35,
default_bar_height = 5,

default_gauge_width = 35,
default_gauge_height = 35,

default_graph_height = 20,

-- Gap between borders of screen and text
-- Add spaces to keep things from moving about? This only affects certain objects.
use_spacer = "none",

-- Subtract file system buffers from used memory?
no_buffers = true,

-- set to = true if you want all text to be in uppercase
uppercase = false,

-- boinc (seti) dir
--seti_dir = "/usr/lib/boinc-app-seti/setiathome_enhanced",
}


--    ${color lightgrey}${hr}
--
--    ${color #42AE4A}Power: ${color lightgrey}${execi 2 acpi | sed -e 's/ .*: //'}

conky.text = [[
${color #42AE4A}$sysname $kernel $machine ${color lightgrey}@${color #42AE4A} $nodename
${color #42AE4A}Uptime:${color lightgrey}$uptime ${color #42AE4A}Load:${color lightgrey}$loadavg
${battery_time}

${color #42AE4A}User       From              Login time
${color red}${execi 4 ${HOME}/bin/my/conky/remote-logins}
${color lightgrey}${hr}

${color #42AE4A}${cpugraph cpu1 15,95 42AE4A eeeeee} ${color #42AE4A} ${alignr}${color #42AE4A}${cpugraph cpu2 15,95 42AE4A eeeeee}
${color #42AE4A}${cpugraph cpu3 15,95 42AE4A eeeeee} ${color #42AE4A} ${alignr}${color #42AE4A}${cpugraph cpu4 15,95 42AE4A eeeeee}
${color #42AE4A}[1]${color lightgrey} ${freq_g cpu1}GHz${color #42AE4A}: (${color lightgrey}${execi 8 sensors | grep 'Core 0' | sed 's>.*: *+\(.*\)\..*(.*>\1>g'}°C${color #42AE4A}) ${alignr}${color #42AE4A}[2]${color lightgrey} ${freq_g cpu2}GHz${color #42AE4A} (${color lightgrey}${execi 8 sensors | grep 'Core 1' | sed 's>.*: *+\(.*\)\..*(.*>\1>g'}°C${color #42AE4A})
${color #42AE4A}[3]${color lightgrey} ${freq_g cpu3}GHz${color #42AE4A}: (${color lightgrey}${execi 8 sensors | grep 'Core 2' | sed 's>.*: *+\(.*\)\..*(.*>\1>g'}°C${color #42AE4A}) ${alignr}${color #42AE4A}[4]${color lightgrey} ${freq_g cpu4}GHz${color #42AE4A} (${color lightgrey}${execi 8 sensors | grep 'Core 3' | sed 's>.*: *+\(.*\)\..*(.*>\1>g'}°C${color #42AE4A})
${color #42AE4A}Average: ${color lightgrey}${freq_g}GHz${color #42AE4A}
${cpugraph cpu0 15,200 42AE4A eeeeee}
${color #42AE4A}Processes:${color lightgrey} $processes ${color #42AE4A}Run:${color lightgrey} $running_processes
${color lightgrey}${hr}

${color #42AE4A}Top CPU usage      PID   CPU%   MEM%${color lightgrey}
${top name 1} ${top pid 1} ${top cpu 1} ${top mem 1}
${top name 2} ${top pid 2} ${top cpu 2} ${top mem 2}
${top name 3} ${top pid 3} ${top cpu 3} ${top mem 3}
${top name 4} ${top pid 4} ${top cpu 4} ${top mem 4}
${top name 5} ${top pid 5} ${top cpu 5} ${top mem 5}
${top name 6} ${top pid 6} ${top cpu 6} ${top mem 6}

${color #42AE4A}Top MEM usage      PID   CPU%   MEM%${color lightgrey}
${top_mem name 1} ${top_mem pid 1} ${top_mem cpu 1} ${top_mem mem 1}
${top_mem name 2} ${top_mem pid 2} ${top_mem cpu 2} ${top_mem mem 2}
${top_mem name 3} ${top_mem pid 3} ${top_mem cpu 3} ${top_mem mem 3}
${top_mem name 4} ${top_mem pid 4} ${top_mem cpu 4} ${top_mem mem 4}
${top_mem name 5} ${top_mem pid 5} ${top_mem cpu 5} ${top_mem mem 5}
${top_mem name 6} ${top_mem pid 6} ${top_mem cpu 6} ${top_mem mem 6}

${color #42AE4A}Top IO  usage      PID    IO%   CPU%${color lightgrey}
${top_io name 1} ${top_io pid 1} ${top_io io_perc 1} ${top_io cpu 1}
${top_io name 2} ${top_io pid 2} ${top_io io_perc 2} ${top_io cpu 2}
${top_io name 3} ${top_io pid 3} ${top_io io_perc 3} ${top_io cpu 3}
${top_io name 4} ${top_io pid 4} ${top_io io_perc 4} ${top_io cpu 4}
${top_io name 5} ${top_io pid 5} ${top_io io_perc 5} ${top_io cpu 5}
${top_io name 6} ${top_io pid 6} ${top_io io_perc 6} ${top_io cpu 6}

${color #42AE4A}RAM      ${color lightgrey}$mem${color #42AE4A} / ${color lightgrey}$memmax${alignr}$memperc% ${color #42AE4A}${membar}
${color #42AE4A}SWAP-HDD ${color lightgrey}${execi 8 ${HOME}/bin/my/conky/fs-stat swap /dev/tia_balabit/swap used}${color #42AE4A} / ${color lightgrey}${execi 8 ${HOME}/bin/my/conky/fs-stat swap /dev/tia_balabit/swap size}${alignr}${execi 8 ${HOME}/bin/my/conky/fs-stat swap /dev/tia_balabit/swap percent}% ${color #42AE4A}${execbar ${HOME}/bin/my/conky/fs-stat swap /dev/tia_balabit/swap percent}
${color lightgrey}${hr}

${color #42AE4A}IOstat       tps   rMB/s   wMB/s
${color lightgrey}${execi 8 ${HOME}/bin/my/conky/io-stat nvme0n1}
${color #42AE4A}${diskiograph 15,200 nvme0n1 42AE4A eeeeee}
${color #42AE4A}HD IO (r,w): ${alignr 40}${color lightgrey}${diskio_read nvme0n1}${color #42AE4A}, ${alignr 20}${color lightgrey}${diskio_write nvme0n1}

${color #42AE4A}Hard Disk Space:
${color #42AE4A} Root      ${color lightgrey}${fs_size /} ${color #42AE4A}/ ${color lightgrey}${fs_free /}${alignr}${fs_used_perc /}% ${color #42AE4A}${fs_bar /}
${color #42AE4A} Boot      ${color lightgrey}${fs_size /boot} ${color #42AE4A}/ ${color lightgrey}${fs_free /boot}${alignr}${fs_used_perc /boot}% ${color #42AE4A}${fs_bar /boot}
${color #42AE4A} EFI       ${color lightgrey}${fs_size /boot/efi} ${color #42AE4A}/ ${color lightgrey}${fs_free /boot/efi}${alignr}${fs_used_perc /boot/efi}% ${color #42AE4A}${fs_bar /boot/efi}
${color #42AE4A} Datastore ${color lightgrey}${fs_size /var/datastore} ${color #42AE4A}/ ${color lightgrey}${fs_free /var/datastore}${alignr}${fs_used_perc /var/datastore}% ${color #42AE4A}${fs_bar /var/datastore}
${color lightgrey}${hr}

${color #42AE4A}[enp0s31f6] ${alignr}[wlp3s0]
${color lightgrey}${addr enp0s31f6} ${alignr}${addr wlp3s0}
${color #42AE4A}${downspeedgraph enp0s31f6 15,95 42AE4A eeeeee 160} ${alignr}${downspeedgraph wlp3s0 15,95 42AE4A eeeeee 160}
${color #42AE4A}D:${color lightgrey} ${downspeed enp0s31f6} /s ${alignr}${color #42AE4A}D:${color lightgrey} ${downspeed wlp3s0} /s
${color #42AE4A}${upspeedgraph enp0s31f6 15,95 42AE4A eeeeee 25} ${alignr}${upspeedgraph wlp3s0 15,95 42AE4A eeeeee 25}
${color #42AE4A}U:${color lightgrey} ${upspeed enp0s31f6} /s ${alignr}${color #42AE4A}U:${color lightgrey} ${upspeed wlp3s0} /s
]]
