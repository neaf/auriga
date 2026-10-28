#!/bin/sh
# Send a touch event to the Auriga OpenAuto capture.
# Usage: aa-tap.sh tap 640 360
#        aa-tap.sh down 640 360
#        aa-tap.sh move 700 380
#        aa-tap.sh up 700 380
# Coordinates are in the 1280x720 AA video space.
set -eu
cmd=${1:-tap}
x=${2:?x coordinate required}
y=${3:?y coordinate required}
ssh -o BatchMode=yes pi@auriga-pi.local "echo '$cmd $x $y' > /tmp/auriga-in"
