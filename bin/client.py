"""This file contains the container accounting client."""

from argparse import ArgumentParser
from configparser import ConfigParser
from datetime import timedelta, datetime
import json
import logging
import requests
import sys

import common
from common.publisher import Publisher
import without_orchestration

root_log = logging.getLogger()
root_log.setLevel(logging.INFO)
ch = logging.StreamHandler(sys.stdout)
fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
formatter = logging.Formatter(fmt)
ch.setFormatter(formatter)
root_log.addHandler(ch)
log = logging.getLogger("client")
logging.getLogger("pika").setLevel(logging.WARNING)


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

    elastic_url = "%s://%s:%s" % (elastic_prefix, elastic_host, elastic_port)

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

            # Save the record, this will intentionally override previous
            # records with the same id.
            # We use requests rather than the elasticsearch python client
            # because it seems the elastic client doesn't handle talking from
            # one container to another.
            index = "%s-%s" % (elastic_index, measurement_day)
            doc_type = 'accounting_data'
            id = record_id

            # Before writing to elasticsearch via requests, we must convert the
            # @timestamp field so it's not a datatime object else json.dumps()
            # fails.
            record["@timestamp"] = record["@timestamp"].isoformat()

            full_put_url = "%s/%s/%s/%s?refresh" % (elastic_url, index, doc_type, id)
            log.debug("Attempting to write data to %s" % full_put_url)
            log.debug("Attempting to write %s" % record)

            response = requests.put(
                full_put_url,
                data=json.dumps(record),
                headers={
                    'Content-Type': 'application/json',
                }
            )

            if response.status_code != 200:
                log.error("Error %s saving to elasticsearch: %s" % (response.status_code, response.text))
                sys.exit(1)

            log.info("Updated data for record: %s" % record_id)

    if arguements.send_accounting_data:
        # Determine yesterdays index to send that data.
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y.%m.%d")
        index = "%s-%s" % (elastic_index, yesterday)

        # Get the site name from the config file to add to records later.
        site_name = config.get("infrastructure", "site_name")

        # The elasticsearch API enforces paging.
        # We page manually because it seems the elastic client doesn't handle
        # talking from one container to another.
        # Work out the total number of hits to expect.
        try:
            total_hits_url = "%s/%s/_search?size=0" % (elastic_url, index)
            response_total_hits = requests.get(total_hits_url).json()
            total_hits = response_total_hits["hits"]["total"]
        except KeyError:
            log.error("Could not find number of total hits from %s" % total_hits_url)
            sys.exit(1)

        # Do the paging.
        fetched_records = []
        while len(fetched_records) < total_hits:
            paged_url = "%s/%s/_search?from=%s" % (elastic_url,
                                                   index,
                                                   len(fetched_records))

            paged_response = requests.get(paged_url).json()
            fetched_records = fetched_records + paged_response["hits"]["hits"]

        # Create a message object to later send.
        # Use copy to avoid pass by reference issues.
        message = common.CONTAINER_USAGE_EMPTY_MESSAGE.copy()

        # Add the site to each record.
        for record in fetched_records:
            record["Site"] = site_name

        message["UsageRecords"] = fetched_records

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
