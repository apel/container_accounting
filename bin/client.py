"""This file contains the container accounting client."""

from argparse import ArgumentParser
from configparser import ConfigParser
from datetime import timedelta, datetime
import json
import logging

from elasticsearch import Elasticsearch
from elasticsearch import helpers as elasticsearch_helpers
from elasticsearch import exceptions as elasticsearch_exceptions

import common
from common.publisher import Publisher
import without_orchestration

log = logging.getLogger(__name__)


def main():
    arguements_parser = ArgumentParser(
        # description=__doc__,
        # version=ver
    )
    arguements_parser.add_argument("-c", "--config",
                                   help="location of the config file",
                                   default="/etc/apel/container/client.cfg")

    arguements_parser.add_argument("--save_monitoring_data",
                                   type=bool,
                                   help="capture monitoring data from an API",
                                   default=False)

    arguements_parser.add_argument("--send_accounting_data",
                                   type=bool,
                                   help="send accounting data to a broker",
                                   default=False)

    arguements = arguements_parser.parse_args()

    config = ConfigParser()
    config.read(arguements.config)

    orchestrator = config.get("infrastructure", "orchestrator")
    if orchestrator == "None":
        APIParserClass = without_orchestration.cadvisor_parser.CadvisorParser
    else:
        raise ValueError("Unsupported orchestrator: %s" % orchestrator)

    # Get details of where accounting data is/will be stored.
    elastic_host = config.get("elasticsearch", "host")
    elastic_port = config.get("elasticsearch", "port")
    elastic_use_ssl = config.getboolean("elasticsearch", "use_ssl")
    elastic_index = config.get("elasticsearch", "index")
    # Does the elasticsearch cluster support/require SSL?
    if elastic_use_ssl:
        elastic_prefix = "https"
    else:
        elastic_prefix = "http"

    # Create an elasticsearch client object to write/read data.
    elastic_client = Elasticsearch(
            hosts=[{"host:": "%s://%s" % (elastic_prefix, elastic_host),
                    "port": elastic_port}]
    )

    if arguements.save_monitoring_data:
        # Get the of details the API to fetch monitoring data from.
        monitoring_host = config.get("monitoring_data", "host")
        monitoring_port = config.get("monitoring_data", "port")
        monitoring_use_ssl = config.getboolean("monitoring_data", "use_ssl")
        monitoring_api_version = config.get("monitoring_data", "api_version")

        # Create an APIParser.
        api_parser = APIParserClass(
            monitoring_host,
            monitoring_port,
            monitoring_use_ssl,
            monitoring_api_version,
        )

        # Parse the API.
        monitoring_data = api_parser.parse_monitoring_data()

        for record in monitoring_data:
            # Determine which elasticsearch index to store the data in based
            # off of the records timestamp.
            measurement_day = record["@timestamp"].strftime("%Y.%m.%d")

            # Ensure we only keep the latest data point per container per day
            # by creating a record ID from the docker ID and the measurement
            # day.
            record_id = "%s-%s" % (record["DockerId"], measurement_day)

            # Save the record, this will override previous records with the
            # same id.
            elastic_client.index(
                index="%s-%s" % (elastic_index, measurement_day),
                doc_type='accounting_data',
                id=record_id,
                body=record,
                refresh=True,
            )

    if arguements.send_accounting_data:
        # Send data stored in yesterdays index.
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y.%m.%d")

        # Get the site name from the config file to add to records later.
        site_name = config.get("infrastructure", "site_name")

        # The elasticsearch API enforces paging, so use an helper function
        # which returns a generator. Errors like no index matching the one
        # provided only manifest when trying to use that generator.
        print("%s-%s" % (elastic_index, yesterday))
        raw_records_generator = elasticsearch_helpers.scan(
            elastic_client,
            index="%s-%s" % (elastic_index, yesterday),
        )

        # Create a message object to later send.
        # Use copy to avoid pass by reference issues.
        message = common.CONTAINER_USAGE_EMPTY_MESSAGE.copy()

        try:
            for raw_record in raw_records_generator:
                record = raw_record["_source"]
                record["Site"] = site_name
                message["UsageRecords"].append(record)
        # Possible cause of this exception is no index matching the one
        # provided to the generator.
        except elasticsearch_exceptions.NotFoundError:
            log.error("No records for yesterday.")

        # Get broker options from config file.
        host = config.get("broker", "host")
        port = config.getint("broker", "port")
        virtual_host = config.get("broker", "virtual_host")
        queue = config.get("broker", "queue")
        username = config.get("broker", "username")
        password = config.get("broker", "password")

        sender = Publisher(host, port, virtual_host, queue, username, password)

        # Can't send a dictionary, so convert to a string.
        string_message = json.dumps(message)
        sender.send(string_message)
        sender.close()


if __name__ == "__main__":
    main()
