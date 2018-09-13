"""This file contains the AgentLogParser class."""

from datetime import datetime
from elasticsearch import Elasticsearch, NotFoundError
import parse


class AgentLogParser(object):
    """A class to parse the Agent Log into partial records."""

    def __init__(self, agent_log_file, elastic_host, elastic_port):
        """Initalise a new AgentLogParser."""
        self.agent_log_file = agent_log_file
        self.elastic = Elasticsearch(hosts=[{"host":elastic_host,
                                             "port":elastic_port}])

    def parse(self):
        """
        Parse an Agent Log File into partial usage records.

        These partial records be JSON containing:
        - Docker Id
        - CreationTime
        - Status
        - WallDuration
        - SuspendDuration
        - LastSeen
        """
        # Store the partial records to return here
        # using the DockerId as the key.
        partial_records_to_return = {}

        # Read the log file into a python list.
        with open(self.agent_log_file) as agent_log_file:
            agent_log = agent_log_file.readlines()

        # All logfiles about containers starting/stopping will have this form
        pattern = parse.compile("time=\"{}\" level={} msg=\"rancher id [{}]: Container with docker id [{}] has been {}\" \n")

        # Attempt to determine when the Agent log was last parsed.
        try:
            last_updated_object = self.elastic.get(index="accounting_agent_logs",
                                                   doc_type="last_updated", id=1)

            last_updated = last_updated_object["_source"]["timestamp"]
            # Make the timestamp a timestamp object for easier timestamp maths.
            last_updated = datetime.strptime(last_updated, "%Y-%m-%dT%H:%M:%S")

        except NotFoundError:
            # Then set last_updated as the earliest date possible.
            last_updated = datetime.min

        print("Parsing from %s onwards" % last_updated)
        # This list will be used to store the Docker Ids of
        # currently running containers.
        currently_running_containers = []

        # There will be end of run processing we only want to do it we have
        # parsed a relevant log line.
        parsed_a_line = False
        # Some of that processing will involve changing the last updated time.
        new_last_updated = last_updated
        for line in agent_log:
            match = pattern.parse(line)
            if match:
                log_time = datetime.strptime(match[0], "%Y-%m-%dT%H:%M:%SZ")
                if log_time <= last_updated:
                    continue
                else:
                    # Then we have parsed atleast one line and we will want to
                    # do some end of run processing.
                    parsed_a_line = True
                    # Set the timestamp of this log line to be the
                    # new last updated time.
                    new_last_updated = log_time

                # We currently don't care about level and the Rancher ID
                # level = match[1]
                # rancher_id = "1i%s" % match[2]
                docker_id = match[3]
                raw_status = match[4]

                # Map Rancher states to "Running" (consuming resource)
                # and "Stopped" (Not consuming resource). This could be
                # extended in the future if there are multiple states that
                # do or do not consume resources.
                if raw_status == "started":
                    incoming_status = "Running"
                elif raw_status == "deactivated":
                    incoming_status = "Stopped"
                else:
                    incoming_status = "unknown"

                # Every time we see a container in the log, we need to
                # retrieve the last state it was in to determine wether to
                # assigned the time inbetween to
                # WallDuration or SuspendDuration.
                try:
                    record_object = self.elastic.search(index="accounting_agent_logs",
                                                        doc_type="accounting",
                                                        body={"query": {"match": {"DockerId": docker_id}}},
                                                        sort='LastSeen:desc')

                    # Get the most recent record for this container.
                    record = record_object["hits"]["hits"][0]["_source"]
                    # Make the text timestamps a timestamp object
                    # for easier timestamp maths.
                    record["LastSeen"] = datetime.strptime(record["LastSeen"], "%Y-%m-%dT%H:%M:%S")
                    record["CreationTime"] = datetime.strptime(record["CreationTime"], "%Y-%m-%dT%H:%M:%S")

                    current_state = record["Status"]

                    if current_state == "Running":
                        # Then any time between the time of the log event and the
                        # "LastSeen" time is WallDuration.
                        record["Status"] = incoming_status
                        record["WallDuration"] += int((log_time - record["LastSeen"]).total_seconds())
                        record["LastSeen"] = log_time

                    elif current_state == "Stopped":
                        # Then any time between the time of the log event and the
                        # "LastSeen" time is SuspendDuration.
                        record["Status"] = incoming_status
                        record["SuspendDuration"] += int((log_time - record["LastSeen"]).total_seconds())
                        record["LastSeen"] = log_time

                    if incoming_status == "Running":
                        # Then add this container to the list of those
                        # currently running.
                        currently_running_containers.append(docker_id)
                    else:
                        # Then remove this container from the list of those
                        # currently running.
                        currently_running_containers.remove(docker_id)

                    # Save the record to the dict of those to be returned
                    partial_records_to_return[docker_id] = record
                    # Save the record back to ElasticSearch.
                    # This may or may not overwrite existing records in
                    # ElasticSearch - which is okay as we want to keep
                    # one record per month.
                    self.elastic.index(index="accounting_agent_logs",
                                       doc_type='accounting',
                                       id="%s-%s-%s" % (log_time.year,
                                                        log_time.month,
                                                        docker_id),
                                       body=record)
                    # After writing to an index, we always need to refresh it
                    # to ensure the data is available for reading.
                    self.elastic.indices.refresh(index="accounting_agent_logs")

                except (IndexError, NotFoundError):
                    # The this line is the most likely the container
                    # starting. So create an initial record.
                    initial_record = {"DockerId": docker_id,
                                      "Status": incoming_status,
                                      "WallDuration": 0,
                                      "SuspendDuration": 0,
                                      "CreationTime": log_time,
                                      "LastSeen": log_time}

                    # Save the initial record to ElasticSearch and the dict
                    # of records to be returned.
                    partial_records_to_return[docker_id] = initial_record
                    self.elastic.index(index="accounting_agent_logs",
                                       doc_type='accounting',
                                       id="%s-%s-%s" % (log_time.year,
                                                        log_time.month,
                                                        docker_id),
                                       body=initial_record)
                    # And add the DockerId to the list of those containers
                    # currently running
                    currently_running_containers.append(docker_id)
                    # After writing to an index, we always need to refresh it
                    # to ensure the data is available for reading.
                    self.elastic.indices.refresh(index="accounting_agent_logs")

        if parsed_a_line:
            # If a container starts and does not get stopped, the above processing wont
            # catch that, as only changes in state get logged.
            # As such, we need to "fudge" it a little bit and assume that the
            # container continues to run until atleast the last log line we parsed.
            for docker_id in currently_running_containers:
                record_object = self.elastic.search(index="accounting_agent_logs",
                                                    doc_type="accounting",
                                                    body={"query": {"match": {"DockerId": docker_id}}},
                                                    sort='LastSeen:desc')

                # Get the most recent record for this container.
                record = record_object["hits"]["hits"][0]["_source"]
                # Make the text timestamps a timestamp object
                # for easier timestamp maths.
                record["LastSeen"] = datetime.strptime(record["LastSeen"], "%Y-%m-%dT%H:%M:%S")
                record["CreationTime"] = datetime.strptime(record["CreationTime"], "%Y-%m-%dT%H:%M:%S")

                record["WallDuration"] += int((new_last_updated - record["LastSeen"]).total_seconds())
                record["LastSeen"] = new_last_updated

                # This may or may not override an exisiting partial record,
                # which is okay as we only want to return
                # one record per DockerId.
                partial_records_to_return[docker_id] = record
                # This may or may not overwrite existing records in
                # ElasticSearch - which is okay as we want to keep
                # one record per month.
                self.elastic.index(index="accounting_agent_logs",
                                   doc_type='accounting',
                                   id="%s-%s-%s" % (log_time.year,
                                                    log_time.month,
                                                    docker_id),
                                   body=record)

                # After writing to an index, we always need to refresh it
                # to ensure the data is available for reading.
                self.elastic.indices.refresh(index="accounting_agent_logs")

            # We shouldn't make the same assumption with "Stopped" containers that
            # don't appear again in the Rancher Agent logs may have been deleted, and
            # hence never start again.
            # If the container is started again, the intermediate time
            # is accounted as SuspendDuration.

            # Update the value stored in ElasticSearch for last_updated
            self.elastic.index(index="accounting_agent_logs",
                               doc_type='last_updated',
                               id=1,
                               body={'timestamp': new_last_updated})

            # After writing to an index, we always need to refresh it
            # to ensure the data is available for reading.
            self.elastic.indices.refresh(index="accounting_agent_logs")

        # Return only the partial records as a list
        return partial_records_to_return.values()
