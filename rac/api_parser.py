"""This file contains the APIParser class."""
import requests


class APIParser(object):
    """A class to extract information from the API."""

    def __init__(self, rancher_host, rancher_port, rancher_api_version):
        """Initalise a new APIParser."""
        self.rancher_host = rancher_host
        self.rancher_port = rancher_port
        self.rancher_api_version = rancher_api_version

    def get_image_id_mapping(self):
        """Get the DockerId and ImageName of all recent containers."""
        response = requests.get("http://%s:%s/%s/containers" %
                                (self.rancher_host, self.rancher_port,
                                 self.rancher_api_version))

        mappings_to_return = {}
        for datapoint in response.json()["data"]:
            mappings_to_return[datapoint["data"]["dockerContainer"]["Id"]] = datapoint["data"]["dockerContainer"]["Image"]

        return mappings_to_return
