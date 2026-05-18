#!/bin/bash

URL=$(cat stream.txt)

ffmpeg \
-reconnect 1 \
-reconnect_streamed 1 \
-reconnect_delay_max 5 \
-i "$URL" \
-c copy \
-f hls \
-hls_time 4 \
-hls_list_size 5 \
/var/www/html/live/stream.m3u8
