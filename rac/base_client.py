"""This file contains the BaseClient class."""

from dirq.QueueSimple import QueueSimple


class BaseClient(object):
    """A base class for a generic APEL collector."""

    def __init__(self, message_directory):
        """Initalise a new BaseClient."""
        self.outgoing_messages = QueueSimple(message_directory)

    def save_records_to_disk(self, record_list):
        """Save records to disk for later sending."""
        # For quickness, just save 1 record per message.
        for record in record_list:
            self.outgoing_messages.add(record)
