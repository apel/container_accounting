"""This file containes the RancherClient class."""
from optparse import OptionParser

from elasticsearch import Elasticsearch, NotFoundError

from rac import BaseClient, AgentLogParser, APIParser

try:
    # Import Python 3 configparser module
    import configparser
except ImportError:
    # Import Python 2 version of the module, but alias it to match the
    # Python 3 version for simplicities sake later on when using the module.
    import ConfigParser as configparser


class RancherClient(BaseClient):
    """A class to interact with Rancher and produce accounting records."""

    def __init__(self, message_directory, config):
        """Initalise a new RancherClient."""

        elastic_host = config.get('elasticsearch', 'local_host')
        elastic_port = int(config.get('elasticsearch', 'local_port'))

        rancher_host = config.get('rancher', 'host')
        rancher_port = int(config.get('rancher', 'port'))
        rancher_api_version = config.get('rancher', 'api_version')
        agent_log_path = config.get('rancher', 'agent_log_path')

        self.agent_log_parser = AgentLogParser(agent_log_path,
                                               elastic_host, elastic_port)

        self.api_parser = APIParser(rancher_host, rancher_port,
                                    rancher_api_version,
                                    elastic_host, elastic_port)

        self.elastic = Elasticsearch(hosts=[{"host": elastic_host,
                                             "port": elastic_port}])

        super(RancherClient, self).__init__(message_directory)

    def create_records(self):
        """
        Return a list of accounting records.

        It does this by combining information from the Agent logs,
        the Rancher API and stored data in an ElasticSearch instance.
        """
        # Get as fresh as possible monitoring data.
        self.api_parser.save_monitoring_data()
        # Get partial records from the Agent Log
        partial_record_list = self.agent_log_parser.parse()
        # Get the DockerId to ImageName mapping from the API.
        mapping_record_dict = self.api_parser.get_image_id_mapping()

        for record in partial_record_list:
            docker_id = record["DockerId"]

            try:
                record["ImageName"] = mapping_record_dict["DockerId"]
            except KeyError:
                # It's *possible* that we have a partial record but
                # no mapping info.
                record["ImageName"] = None

            month = record["LastSeen"].month
            year = record["LastSeen"].year

            try:
                monitoring_info = self.elastic.get(index="accounting_monitoring_information",
                                                   doc_type="accounting",
                                                   id="%s-%s-%s" % (year, month, docker_id))

                for key in monitoring_info["_source"]:
                    if key != "DockerId":
                        record[key] = monitoring_info["_source"][key]

            except NotFoundError:
                # This code pattern is bad and the lack of monitoring data
                # should be logged.
                pass

            self.elastic.index(index="local_accounting_records",
                               doc_type='accounting',
                               id="%s-%s-%s" % (year,
                                                month,
                                                docker_id),
                               body=record)

            self.elastic.indices.refresh(index="local_accounting_records")


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

    CLIENT = RancherClient('/tmp/apel/outgoing', config)
    CLIENT.create_records()
