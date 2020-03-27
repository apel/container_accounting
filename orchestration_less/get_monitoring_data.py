"This file parses the cadvisor api to save useful accounting data."

from datetime import datetime
import json
import logging
import sys

from elasticsearch import Elasticsearch
import requests

# Set up logging
logging.basicConfig(level=logging.DEBUG)
# Limit requests logging to warning.
logging.getLogger(
    "urllib3.connectionpool"
).setLevel(logging.WARN)
# Limit elasticsearch logging to warning.
logging.getLogger(
    "elasticsearch"
).setLevel(logging.WARN)

log = logging.getLogger(__name__)

CADVISOR_HOST = "host-172-16-113-140.nubes.stfc.ac.uk"
CADVISOR_HOST_HTTPS_ENABLED = False
CADVISOR_PORT = "80"
CADVISOR_API_VERSION = "1.3"

ELASTIC_HOST = "host-172-16-113-140.nubes.stfc.ac.uk"
ELASTIC_HOST_HTTPS_ENABLED = False
ELASTIC_PORT = "9200"
ELASTIC_INDEX = "local_sdc_accounting"

if ELASTIC_HOST_HTTPS_ENABLED:
    ELASTIC_CLIENT = Elasticsearch(
        hosts=[{"host:": "https://%s" % ELASTIC_HOST, "port": 9200}]
    )
else:
    ELASTIC_CLIENT = Elasticsearch(
        hosts=[{"host:": "http://%s" % ELASTIC_HOST, "port": 9200}]
    )

if CADVISOR_HOST_HTTPS_ENABLED:
    CADVISOR_URL = "https://%s:%s/api/v%s" % (CADVISOR_HOST,
                                              CADVISOR_PORT,
                                              CADVISOR_API_VERSION)
else:
    CADVISOR_URL = "http://%s:%s/api/v%s" % (CADVISOR_HOST,
                                             CADVISOR_PORT,
                                             CADVISOR_API_VERSION)

log.info("Fetching monitoring data from %s." % CADVISOR_URL)

data = []
# Get information from the cadvisor "docker" API.
response_object = requests.get("%s/docker/" % CADVISOR_URL)

if response_object.status_code != 200:
    log.error("Got status code: %s, aborting." % response_object.status_code)
    sys.exit(-1)

# Parse the response.
response_data = json.loads(response_object.text)
# The valuse of response_data contain the relevant data on the running
# containers.
for running_container in response_data.values():
    container_info = {}

    measurement_time = datetime.now()
    container_info["@timestamp"] = measurement_time.isoformat()

    container_info["DockerId"] = running_container["id"]

    # We can pluck the container name from the monitoring info if we want.
    # Given the lack of orchestrator, we have to rely on the monitoring
    # info for this.
    container_info["Name"] = running_container["aliases"][0]
    # We can pluck the image name from the monitoring info if we want.
    # Given the lack of orchestrator, we have to rely on the monitoring
    # info for this.
    container_info["ImageName"] = running_container["spec"]["image"]

    # Get the latest usage statistics.
    latest_stats = running_container["stats"][-1:][0]
    # Parse CpuDuration (in seconds) from the latest usage statistics.
    cpu_duration_nanoseconds = latest_stats["cpu"]["usage"]["total"]
    container_info["CpuDuration"] = int(cpu_duration_nanoseconds / 1e9)
    # Parse StorageUsed (in bytes) from the latest usage statistics.
    # Does this need to be summed across all latest_stats["filesystem"][X]?
    # Maybe? Maybe not?
    container_info["StorageUsed"] = latest_stats["filesystem"][0]["usage"]
    # Parse NetworkInbound and NetworkOutbound from the latest usage
    # statistics.
    container_info["NetworkInbound"] = latest_stats["network"]["rx_bytes"]
    container_info["NetworkOutbound"] = latest_stats["network"]["tx_bytes"]

    measurement_day = measurement_time.strftime("%Y.%m.%d")
    record_id = "%s-%s" % (container_info["DockerId"], measurement_day)

    # Insert the data into elasticsearch.
    ELASTIC_CLIENT.index(
        index="%s-%s" % (ELASTIC_INDEX, measurement_day),
        doc_type='accounting_data',
        id=record_id,
        body=container_info,
    )
