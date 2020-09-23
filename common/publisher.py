import logging
import pika


log = logging.getLogger("publisher")

class Publisher():
    def __init__(self, host, port, virtual_host, queue, username, password):
        credentials = pika.PlainCredentials(username, password)
        parameters = pika.ConnectionParameters(host=host,
                                               port=port,
                                               virtual_host=virtual_host,
                                               credentials=credentials)

        self._connection = pika.BlockingConnection(parameters)
        self._channel = self._connection.channel()
        self._queue = queue
        self._channel.queue_declare(queue=queue, durable="True")

    def send(self, message):
        self._channel.basic_publish(exchange="",  # this is some arcane magic
                                    routing_key=self._queue,
                                    body=message)

        log.info("Sent message")

    def close(self):
        self._connection.close()
