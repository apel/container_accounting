#!/bin/sh
# This is a script to be run as the entrypoint to the docker image.
# It will run:
# - `python3 bin/client.py -c conf/client.cfg --save_monitoring_data True`
#   every minute to capture monitoring data. This must be done very frequently,
#   as the monitoring data can disappear when the container it corresponds to
#   is deleted.
# - `python3 bin/client.py -c conf/client.cfg --send_accounting_data True`
#   every day to send accounting data.

set -eu

minute=`date +"%M"`
day=`date +"%d"`

while true
do
    # Detect if a minute has passed.
    new_minute=`date +"%M"`
    if [ $minute != $new_minute ]; then
      # Save monitoring data.
      python3 bin/client.py -c conf/client.cfg --save_monitoring_data True
      # For testing, send accounting data a lot.
      python3 bin/client.py -c conf/client.cfg --send_accounting_data True
      minute=$new_minute
    fi

    # Detect if an day has passed.    
    new_day=`date +"%d"`
    if [ $day != $new_day ]; then
      # Send accounting data.
      python3 bin/client.py -c conf/client.cfg --send_accounting_data True

      day=$new_day
    fi
done
