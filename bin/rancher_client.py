"""This file containes the RancherClient class."""

from elasticsearch import Elasticsearch, NotFoundError

from rac import BaseClient, AgentLogParser, APIParser

AGENT_LOG_PATH = "agent_log.example"
ELASTIC_HOST = "localhost"
ELASTIC_PORT = "9200"

RANCHER_HOST = "localhost"
RANCHER_PORT = 8080
RANCHER_API_VERSION = "v1"

class RancherClient(BaseClient):
    """A class to interact with Rancher and produce accounting records."""

    def __init__(self, message_directory):
        """Initalise a new RancherClient."""
        self.agent_log_parser = AgentLogParser(AGENT_LOG_PATH,
                                               ELASTIC_HOST, ELASTIC_PORT)

        self.api_parser = APIParser(RANCHER_HOST, RANCHER_PORT,
                                    RANCHER_API_VERSION,
                                    ELASTIC_HOST, ELASTIC_PORT)

        self.elastic = Elasticsearch(hosts=[{"host":ELASTIC_HOST,
                                             "port":ELASTIC_PORT}])

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

    CLIENT = RancherClient('/tmp/apel/outgoing')
    CLIENT.create_records()
