#!/bin/sh

# A simple scrip to pass the stored return code of the python process back to
# the caller for the purposes of a container health check.

exit `cat status.txt`

