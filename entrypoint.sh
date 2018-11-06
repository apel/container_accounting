#!/bin/sh
# This is a script to be run as the entrypoint to the docker image.
# It will run:
# - bin/save_monitoring_data.py every minute to capture data monitroing
#   data from Rancher's API. Thi sust be done very frequently, as the
#   monitoring data disappears when the container ir corresponds to
#   is deleted.
# - bin/rancher_client.py every day to parse Rancher's API and agent log.
#   This can be done daily as Rancher "remembers" containers previously
#   run for longer than a day sufficently that we need only query the API
#   once a day.

set -eu

minute=`date +"%M"`
day=`date +"%d"`

while true
do
    # Detect if a minute has passed.
    new_minute=`date +"%M"`
    if [ $minute != $new_minute ]; then
      bin/save_monitoring_data.py

      minute=$new_minute
    fi

    # Detect if an hour has passed.    
    new_day=`date +"%d"`
    if [ $day != $new_day ]; then
      bin/rancher_client.py

      day=$new_day
    fi
done
