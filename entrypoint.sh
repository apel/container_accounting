#!/bin/sh
# This is a script to be run as the entrypoint to the docker image.
# It will run `python3 bin/client.py -c conf/client.cfg at the
# configured rate to capture and send monitoring data. The exact
# depends on the amount of usage you are accounting for and how
# much you are happy to risk loosing, as the monitoring data
# can disappear when the container it corresponds to is deleted.

set -eu

while true
do
    # Publish
    python3 bin/client.py -c conf/client.cfg
    # Wait the configured time before publishing again.
    sleep $PUBLISH_FREQUENCY
done
