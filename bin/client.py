"""This file contains the container accounting client."""

from argparse import ArgumentParser
from configparser import ConfigParser
from datetime import timedelta, datetime
import json
import logging
import requests
import sys
import time

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

    arguements = arguements_parser.parse_args()

    config = ConfigParser()
    config.read(arguements.config)

    orchestrator = config.get("infrastructure", "orchestrator")
    if orchestrator == "None":
        APIParserClass = without_orchestration.cadvisor_parser.CadvisorParser
    else:
        raise ValueError("Unsupported orchestrator: %s" % orchestrator)

    # Get the site name from the config file to add to records later.
    site_name = config.get("infrastructure", "site_name")

    # Get details of where accounting data will be stored.
    elastic_host = config.get("elasticsearch", "host")
    elastic_port = config.get("elasticsearch", "port")
    elastic_use_ssl = config.getboolean("elasticsearch", "use_ssl")
    elastic_index = "accounting-records-%s" % (site_name.lower())

    # Make an sesison to handle elasticsearch based requests.
    elastic_session = requests.Session()

    # Does the elasticsearch cluster support/require SSL?
    if elastic_use_ssl:
        elastic_prefix = "https"
        elastic_session.verify = "/etc/grid-security/certificates"
    else:
        elastic_prefix = "http"

    elastic_url = "%s://%s:%s" % (elastic_prefix, elastic_host, elastic_port)

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
        # Check that this new record does not decrease any previously
        # reported usage. To do this, we need to search previous indices for
        # the docker ID. To prevent overwhelming elasticsearch, we limit this
        # search to the previous and current month.
        now = datetime.now()
        current_year_month = now.strftime("%Y.%m")
        previous_year_month = now.replace(
            year=now.year if now.month > 1 else now.year - 1,
            month=now.month - 1 if now.month > 1 else 12,
        ).strftime("%Y.%m")

        index = "%s-%s.*,%s-%s.*" % (
            elastic_index, current_year_month,
            elastic_index, previous_year_month
        )

        docker_id = record["DockerId"]
        existing_record = _es_find(
            elastic_session, elastic_url, index, "DockerId", docker_id
        )

        # If an existing record was found
        if existing_record:
            # Look for a drop in reported usage.
            for resource in ["CpuDuration", "NetworkInbound",
                             "NetworkOutbound"]:
                # If it does, we want to seperate it from previous records
                # for this container to prevent any usage going unreported.
                if existing_record[resource] > record[resource]:
                    record["Instance"] = existing_record["Instance"] + 1
                    # No need to keep checking different resoucres if one
                    # has decreased.
                    break
                else:
                    # Assume the same instance as before.
                    # This may intentionally get overwritten when we check
                    # a different resource as part of the for loop.
                    record["Instance"] = existing_record["Instance"]

        else:
            # Mark this record as the first "instance" of the container id
            record["Instance"] = 1

        # Determine which elasticsearch index to store the data in based
        # off of the records timestamp.
        measurement_day = record["@timestamp"].strftime("%Y.%m.%d")
        index = "%s-%s" % (elastic_index, measurement_day)

        # Construct a document id to save this record under.
        record_id = "%s-%s-%s-%s" % (
            site_name, record["DockerId"], measurement_day, record["Instance"]
        )

        # Before writing to elasticsearch, we must convert the @timestamp
        # field so it's not a datatime object else json.dumps() fails.
        record["@timestamp"] = record["@timestamp"].isoformat()

        # Add the site name to the record.
        record["Site"] = site_name

        # Save the record, this will intentionally override previous
        # records with the same id.
        doc_type = 'accounting_data'

        full_put_url = "%s/%s/%s/%s?refresh" % (
            elastic_url, index, doc_type, record_id
        )

        log.debug("Attempting to write data to %s" % full_put_url)
        log.debug("Attempting to write %s" % record)

        response = elastic_session.put(
            full_put_url,
            data=json.dumps(record),
            headers={
                'Content-Type': 'application/json',
            }
        )

        if response.status_code not in [200, 201]:
            log.error("Error %s saving to elasticsearch: %s" % (response.status_code, response.text))
            sys.exit(1)

        log.info("Updated data for record: %s" % record_id)


def _es_find(elastic_session, node, index, field, term):
    """
    Return the newest document that contain an exact term in a provided field.

    Return {} if no document found via searching the supplied node and index.
    """
    # First query if the index exists.
    head_url = node + "/" + index
    max_attempts = 5

    for attempt in range(1, max_attempts+1):
        log.debug("Attempt number: %i", attempt)
        try:
            head_response = elastic_session.head(head_url)
        except requests.exceptions.ConnectionError:
            log.info(
                "A connection error occured with %s, %s, %s, %s.",
                node, index, field, term
            )
            head_response = None  # To be handled later

        if head_response is None or head_response.status_code == 404:
            # Then we haven't found the index, there are two possible causes.
            # 1. The index truly does not exist.
            if attempt == max_attempts:
                log.info("Repeatedly could not find index at: %s" % head_url)
                log.info("index probably doesnt exist")
                return {}
            # 2. The elasticsearch node is still starting up and can't serve
            #    the index just yet. In this case, we simply want to wait and
            #    try again.
            time.sleep(2**attempt)
            continue
        elif head_response.status_code == 200:
            # Then the rest of the while loop can continue.
            break
        else:
            # If we don't get a 200, a 404 or a connection error, then an
            # unexpected error has occured.
            log.error("Unexpected error finding index: %s" % head_url)
            sys.exit(1)

    # Now, we can asusme the index exists and proceed constructing our query
    # data and headers.
    data = {
        "query": {
            "term": {
                field: term
            }
        },
        "sort": [
            {
                "@timestamp": {
                    "order": "desc",
                }
            }
        ],
        "size": 1,
    }

    headers = {
        "Content-Type": "application/json",
    }

    search_url = node + "/" + index + "/_search"
    search_response = elastic_session.get(
        search_url, headers=headers, data=json.dumps(data)
    )

    search_response_json = json.loads(search_response.text)
    search_hit_list = search_response_json["hits"]["hits"]

    if len(search_hit_list) == 0:
        log.debug(
            "No results found for %s %s %s %s", node, index, field, term
        )
        return {}

    if len(search_hit_list) > 1:
        log.error(
            "Too many results found for %s %s %s %s", node, index, field, term
        )
        sys.exit(1)

    return search_hit_list[0]["_source"]


if __name__ == "__main__":
    main()
