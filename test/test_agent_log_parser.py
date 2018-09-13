import datetime
from elasticsearch import Elasticsearch
import unittest
import tempfile
import time
import os
import requests

from rac.agent_log_parser import AgentLogParser

ELASTIC_HOST = "localhost"
ELASTIC_PORT = 9200


class TestAgentLogParser(unittest.TestCase):

    def setUp(self):
        self.elastic = Elasticsearch(hosts=[{"host": ELASTIC_HOST,
                                             "port": ELASTIC_PORT}])

    def test_parsing(self):
        """
        Test the AgentLogParser's main parse method.

        The test log file spans several months. The test is limited to checking
        the final records for each container, not any intermediate records
        saved in ElasticSearch.

        For example:
            Container A starts in Jan2018 and end stops in Dec2018.
            Two records would be saved to ElasticSearch - one for Jan and one
            December, but this test will only check the usage was properly
            accounted in the December record. i.e. the usage recorded is
            eventually correct.
        """
        log_text = self._generate_log_text()

        _temp_log_file, temp_log_path = tempfile.mkstemp()
        with open(temp_log_path, 'w') as open_temp_log_file:
            open_temp_log_file.write(log_text)

        parser = AgentLogParser(temp_log_path, ELASTIC_HOST, ELASTIC_PORT)
        partial_records = parser.parse()

        for record in partial_records:
            docker_id = record['DockerId']
            # Can't just compare the dictionaries due to unicode vs byte
            # incodings, this isn't a problem under Python 3.
            # Python 2 and 3 comparison
            for key in record:
                self.assertEqual(record[key], EXPECTED_RESULTS[docker_id][key])
            # Currently unusable Python 3 only comparison
            # self.assertEqual(record, EXPECTED_RESULTS[docker_id])

    def tearDown(self):
        """Delete index (and the data within) created by the test."""
        self.elastic.indices.delete(index='accounting_agent_logs')

    def _generate_log_text(self):
        """Generate text for an test rancher agent log file."""

        log_text = ''
        # Build up a log file.
        for log_datum in LOG_DATA:
            log_text = log_text + (LOG_LINE_TEMPLATE % log_datum)

        return log_text


# The log lines wish to parse all have the following form.
LOG_LINE_TEMPLATE = 'time="%s" level=info msg="rancher id [%s]: Container with docker id [%s] has been %s" \n'

# The following (time, rancher_id, docker_id, status) tuples will be
# used to generate a log file for testing against.
# The list should be sorted in ascending time order to ensure the generated
# log is in ascending time order.
LOG_DATA = [('2018-01-01T00:00:00Z', '1', 'A', 'started'),
            # Container B starts
            ('2018-01-02T01:00:00Z', '2', 'B', 'started'),
            # Container B stops after an hour.
            ('2018-01-02T02:00:00Z', '2', 'B', 'deactivated'),
            # Container B starts again. The time inbetween should count as
            # SuspendDuration.
            ('2018-12-31T00:00:00Z', '2', 'B', 'started'),
            # Container B stops again after another hour. It should not
            # gain any further SuspendDuration as we cannot be sure it hasn't
            # been deleted.
            ('2018-12-31T01:00:00Z', '2', 'B', 'deactivated'),
            ('2018-12-31T23:59:59Z', '1', 'A', 'deactivated')]

# The partial records we expect to be returned from an AgentLogParser, given
# the above LOG_DATA.
EXPECTED_RESULTS = {}
EXPECTED_RESULTS["A"] = {
    'Status': 'Stopped',
    'CreationTime': datetime.datetime(2018, 1, 1, 0, 0, 0),
    'SuspendDuration': 0,
    'LastSeen': datetime.datetime(2018, 12, 31, 23, 59, 59),
    'WallDuration': 31535999,
    'DockerId': 'A'
}
EXPECTED_RESULTS["B"] = {
    'Status': 'Stopped',
    'CreationTime': datetime.datetime(2018, 1, 2, 1, 0, 0),
    'SuspendDuration': 31356000,
    'LastSeen': datetime.datetime(2018, 12, 31, 1, 0, 0),
    'WallDuration': 7200,
    'DockerId': 'B'
}

if __name__ == "__main__":
    unittest.main()
