"""This file contains a small script to save Rancher monitoring data."""
from rac import APIParser

AGENT_LOG_PATH = "agent_log.example"
ELASTIC_HOST = "localhost"
ELASTIC_PORT = 9200

RANCHER_HOST = "localhost"
RANCHER_PORT = 8080
RANCHER_API_VERSION = "v1"

if __name__ == "__main__":
    API_PARSER = APIParser(RANCHER_HOST, RANCHER_PORT,
                           RANCHER_API_VERSION,
                           ELASTIC_HOST, ELASTIC_PORT)

    API_PARSER.save_monitoring_data()
