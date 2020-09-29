#!/bin/sh
# This is a script to be run as the entrypoint to the docker image.
# It will run `python3 bin/client.py -c conf/client.cfg every
# minute to capture and send monitoring data. This must be done
# very frequently, as the monitoring data can disappear when the
# container it corresponds to is deleted.

set -eu

minute=`date +"%M"`

while true
do
    # Detect if a minute has passed.
    new_minute=`date +"%M"`
    if [ $minute != $new_minute ]; then
      # Save monitoring data.
      python3 bin/client.py -c conf/client.cfg
      minute=$new_minute
    fi
done
