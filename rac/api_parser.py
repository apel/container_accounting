"""This file contains the APIParser class."""
from datetime import datetime
import json
import requests

from elasticsearch import Elasticsearch
from websocket import create_connection


class APIParser(object):
    """A class to extract information from the API."""

    def __init__(self, rancher_host, rancher_port, rancher_api_version,
                 elastic_host, elastic_port):
        """Initalise a new APIParser."""
        self.rancher_host = rancher_host
        self.rancher_port = rancher_port
        self.rancher_api_version = rancher_api_version
        self.elastic = Elasticsearch(hosts=[{"host":elastic_host,
                                             "port":elastic_port}])

    def get_image_id_mapping(self):
        """Get the DockerId and ImageName of all recent containers."""
        response = requests.get("http://%s:%s/%s/containers" %
                                (self.rancher_host, self.rancher_port,
                                 self.rancher_api_version))

        mappings_to_return = {}
        for datapoint in response.json()["data"]:
            mappings_to_return[datapoint["data"]["dockerContainer"]["Id"]] = datapoint["data"]["dockerContainer"]["Image"]

        return mappings_to_return

    def save_monitoring_data(self):
        """Save a snapshot of the montioring data and save to ElasticSearch."""
        response = requests.get("http://%s:%s/%s/containers" %
                                (self.rancher_host, self.rancher_port,
                                 self.rancher_api_version))

        # Get the Rancher IDs of currently running
        # and recently exited containers.
        rancher_id_list = []
        for datapoint in response.json()["data"]:
            # Each datapoint contains all the information the Rancher API
            # can provide for a single container.
            # Store the Rancher ID of the container for future API calls
            rancher_id_list.append(datapoint["id"])

        for rancher_id in rancher_id_list:
            # Get the container stats page
            response = requests.get("http://%s:%s/%s/containers/%s/containerstats" %
                                    (self.rancher_host, self.rancher_port,
                                     self.rancher_api_version, rancher_id))

            container_stats = response.json()
            # Work out the websocket link and token to access it
            token = container_stats["token"]
            monitoring_url = container_stats["url"]

            # Get the latest monitoring data
            web_socket = create_connection("%s?token=%s" % (monitoring_url, token))
            # web_socket.recv() returns a list. I am assuming that the list is always
            # size 1. If that is a false assumption, this will fail loudly.
            [monitoring_data] = json.loads(web_socket.recv())
            # close the connection
            web_socket.close()

            # Create a dictionary containing metrics.
            metric_dictionary = {}

            try:
                metric_dictionary["DockerId"] = monitoring_data["id"]
                # The monitoring data is in nanoseconds and we want seconds.
                metric_dictionary["CpuDuration"] = int(monitoring_data["cpu"]["usage"]["total"] * 0.000000001)
                # The monitoring data is in Bytes.
                metric_dictionary["StorageUsed"] = monitoring_data["memory"]["usage"]

                # There seems to be a nice way to get the total rx and tx bytes, but it
                # doesn't seem to be set properly in the JSON returned by the API.
                # So I am summing all the individual interfaces.
                rx_bytes = 0
                tx_bytes = 0
                for interface in monitoring_data["network"]["interfaces"]:
                    rx_bytes = rx_bytes + interface["rx_bytes"]
                    tx_bytes = tx_bytes + interface["tx_bytes"]

                metric_dictionary["NetworkInbound"] = rx_bytes
                metric_dictionary["NetworkOutbound"] = tx_bytes

                # Rancher monitoring timestamps have nanoseconds!
                # pythons datetime can't cope with that so we need
                # to strip them from the timestamp before
                # creating a datetime object.
                measurement_time = datetime.strptime(monitoring_data["timestamp"][:-4]+monitoring_data["timestamp"][-1:],
                                                     "%Y-%m-%dT%H:%M:%S.%fZ")

                self.elastic.index(index="accounting_monitoring_information",
                                   doc_type='accounting',
                                   id="%s-%s-%s" % (measurement_time.year,
                                                    measurement_time.month,
                                                    metric_dictionary["DockerId"]),
                                   body=metric_dictionary)

                # After writing to an index, we always need to refresh it
                # to ensure the data is available for reading.
                self.elastic.indices.refresh(index="accounting_monitoring_information")

            except KeyError:
                # This is bad, should be logged.
                # KeyError might happen if Rancher knows about the container
                # but the container has stopped so there is no monitoring.
                pass
