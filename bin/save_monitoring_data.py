#!/usr/bin/env python2

"""This file contains a small script to save Rancher monitoring data."""
from optparse import OptionParser
from rac import APIParser

try:
    # Import Python 3 configparser module
    import configparser
except ImportError:
    # Import Python 2 version of the module, but alias it to match the
    # Python 3 version for simplicities sake later on when using the module.
    import ConfigParser as configparser

AGENT_LOG_PATH = "agent_log.example"
ELASTIC_HOST = "localhost"
ELASTIC_PORT = 9200

RANCHER_HOST = "localhost"
RANCHER_PORT = 8080
RANCHER_API_VERSION = "v1"

if __name__ == "__main__":

    optparse = OptionParser()
    optparse.add_option('-r', '--rancher_config',
                        help='location of the rancher.cfg file',
                        default='/etc/apel/rancher.cfg')

    optparse.add_option('-e', '--elastic_config',
                        help='location of the elastic.cfg file',
                        default='/etc/apel/elastic.cfg')

    options, unused_args = optparse.parse_args()

    config = configparser.ConfigParser()
    config.read([options.elastic_config, options.rancher_config])

    elastic_host = config.get('elasticsearch', 'local_host')
    elastic_port = int(config.get('elasticsearch', 'local_port'))

    rancher_host = config.get('rancher', 'host')
    rancher_port = int(config.get('rancher', 'port'))
    rancher_api_version = config.get('rancher', 'api_version')

    API_PARSER = APIParser(rancher_host, rancher_port,
                           rancher_api_version,
                           elastic_host, elastic_port)

    API_PARSER.save_monitoring_data()
