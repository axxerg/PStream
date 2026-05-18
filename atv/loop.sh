#!/bin/bash

while true
do
    python3 token.py

    pkill ffmpeg

    ./start.sh &

    sleep 300
done
