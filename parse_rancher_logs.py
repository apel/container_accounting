from datetime import datetime

import parse

from mock_record import MockRecord

RANCHER_AGENT_LOG_FILE = "agent_log-example.log"

with open(RANCHER_AGENT_LOG_FILE) as rancher_agent_log_file:
    rancher_agent_log = rancher_agent_log_file.readlines()

# All logfiles about containers starting/stopping will have this form
pattern = parse.compile("time=\"{}\" level={} msg=\"rancher id [{}]: Container with docker id [{}] has been {}\" \n")

simpler_log = []
parsed_records = {}
last_updated = None # Could be replaced bt a database table later

for line in rancher_agent_log:
    match = pattern.parse(line)
    if match:
        time = datetime.strptime(match[0], "%Y-%m-%dT%H:%M:%SZ")
        # We currently don't care about level and the Rancher ID
        # level = match[1]
        # rancher_id = "1i%s" % match[2]
        docker_id = match[3]
        raw_status = match[4]

        if raw_status == "started":
            incoming_status = "Running"
        elif raw_status == "deactivated":
            incoming_status = "Stopped"
        else:
            incoming_status = "unknown"

        last_updated = time
        print time, docker_id, incoming_status

        try:
            record = parsed_records[docker_id]
            current_state = record._record_content["Status"]

            if current_state == "Running":
                    # Then any time between the time of the log event and the
                    # "LastSeen" time is WallDuration.
                if incoming_status == "Running" or incoming_status == "Stopped":
                    record._record_content["Status"] = incoming_status
                    record._record_content["WallDuration"] += int((time - record._record_content["LastSeen"]).total_seconds())
                    record._record_content["LastSeen"] = time

                else:
                    pass

            elif current_state == "Stopped":
                # Then any time between the time of the log event and the
                # "LastSeen" time is SuspendDuration.
                if incoming_status == "Running" or incoming_status == "Stopped":
                    record._record_content["Status"] = incoming_status
                    record._record_content["SuspendDuration"] += int((time - record._record_content["LastSeen"]).total_seconds())
                    record._record_content["LastSeen"] = time

                else:
                    pass

            else:
                pass

        except KeyError:
            # The this line is the most likely the container starting.
            record = MockRecord()
            record._record_content["Docker Id"] = docker_id
            record._record_content["Status"] = incoming_status
            record._record_content["WallDuration"] = 0
            record._record_content["SuspendDuration"] = 0
            record._record_content["CreationTime"] = time
            record._record_content["LastSeen"] = time
            parsed_records[docker_id] = record

for _, record in parsed_records.items():
    # If a container starts and does not get stopped, the above processing wont
    # catch that, as only changes in state get logged.
    # As such, we need to "fudge" it a little bit and assume that the
    # container continues to run until atleast the last log line we parsed.
    if record._record_content["Status"] == "Running":
        # The Rancher Agent doesn't log microseconds, so we remove them here.
        record._record_content["WallDuration"] += int((last_updated - record._record_content["LastSeen"]).total_seconds())
        record._record_content["LastSeen"] = last_updated

    # We shouldn't make the same assumption with "Stopped" containers that
    # don't appear again in the Rancher Agent logs may have been deleted, and
    # hence never start again.
    # If the container is started again, the intermediate time
    # is accounted as SuspendDuration.

# temp code for printing data to the screen.
print("")
for docker_id, record in parsed_records.items():
    for field, value in record._record_content.items():
        print "%s: %s" % (field, value)
    print
