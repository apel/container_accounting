import elasticsearch
from elasticsearch import Elasticsearch

from datetime import datetime

if __name__ == "__main__":
    # get a client
    es = Elasticsearch(hosts=[{"host":"localhost", "port":"9200"}])
    # add a test message to the index
    es.index(index='container_accounting',
             doc_type='data',
             body={'text': "Hello, World!",
                   '@timestamp': datetime.now()})
