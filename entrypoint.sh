#!/bin/sh
# This is a script to be run as the entrypoint to the docker image.
# It will run `python3 bin/client.py -c conf/client.cfg at the
# configured rate to capture and send monitoring data. The exact
# depends on the amount of usage you are accounting for and how
# much you are happy to risk loosing, as the monitoring data
# can disappear when the container it corresponds to is deleted.

while true
do
    python3 bin/client.py -c conf/client.cfg
    # Store the return code of the python command in a file to reference
    # in the containers health check function.
    echo $? > status.txt
    # Wait the configured time before publishing again.
    sleep $PUBLISH_FREQUENCY
done
