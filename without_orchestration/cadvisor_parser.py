"""
This file containers the parser for an orchestrator less infrastructure.

As there is no orchestrator, there is no orchestrator log to parse.

It assumes a cAdvisor like API is being used to gather monitoring style data
about the running containers, from which accounting data can be produced.
"""

from datetime import datetime
import json
import logging
import requests

log = logging.getLogger(__name__)


class CadvisorParser():
    def __init__(self, host, port, use_ssl, api_version):
        if use_ssl:
            self._cadvisor_url = "https://%s:%s/api/v%s" % (host,
                                                            port,
                                                            api_version)
        else:
            self._cadvisor_url = "http://%s:%s/api/v%s" % (host,
                                                           port,
                                                           api_version)

    def parse_monitoring_data(self):
        data = []
        # Get information from the cadvisor "docker" API.
        response_object = requests.get("%s/docker/" % self._cadvisor_url)

        if response_object.status_code != 200:
            log.error("Got status code: %s, aborting." % response_object.status_code)
            return []

        # Parse the response.
        response_data = json.loads(response_object.text)
        # The valuse of response_data contain the relevant data on the running
        # containers.
        for running_container in response_data.values():
            container_info = {}

            # The creation time of the container.
            container_info["CreationTime"] = running_container["spec"]["creation_time"]

            container_info["@timestamp"] = datetime.now()
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

            data.append(container_info)

        return data
