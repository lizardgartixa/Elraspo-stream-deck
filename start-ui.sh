#!/bin/bash

xrandr --output DSI-1 --mode 720x1280 --rotate left
sleep 2

DISPLAY=:0 xinput set-prop 6 "Coordinate Transformation Matrix" 0 -1 1 1 0 0 0 0 1

unclutter -idle 0 &

chromium --noerrdialogs \
         --disable-infobars \
         --kiosk \
         --no-first-run \
         --disable-translate \
         --force-device-scale-factor=1 \
         --start-fullscreen \
         --window-position=0,0 \
         --window-size=1280,720 \
         http://localhost:5000