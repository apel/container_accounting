# container_accounting

The below documentation assumes deploying the entire system as docker containers. Other deployment methods (such as using non-containerized versions of the software) is theoretically possible, but not supported.

Running the container accounting collector involves running three containers.
1. elasticsearch 6.8.6
1. cAdvisor 0.35.0
1. an APEL container

The APEL container:
* Periodically and frequently polls the cAdvisor API to "monitor" the running containers, storing one measurement per container per day in elasticsearch.
* Periodically sends this data to a central server. 

## Running the container accounting collector

To run the container accounting collector
1. Make sure you have the latest versions of the [docker-compose.yml](docker-compose.yml) file and the [client.cfg](conf/client.cfg) file. Further instructions will assume a directory structre as follows
```
    .
    |__ docker-compose.yml
    |__ conf
        |__ client.cfg
```

2. Pull the latest images.
```
docker-compose.yml pull
```

3. Make a directory to persistently store your elasticsearch data.
```
mkdir ./elasticsearch-data
```

4. Make the directory owned by the elasticsearch user used by the container process.
```
chown 1000:1000 ./elasticsearch-data
```

5. Edit `conf/client.cfg`
  * set `site_name` to a meaningful, human readable, identifier for your site. This will be visible in the accounting dashboard.
  * set the broker details.

6. Edit `docker-compose.yml` to suit your exact deployment
  * You'll need to replace `./conf/client.cfg` with the absolute path.

7. Run the three containers
```
docker-compose up -d elasticsearch
docker-compose up -d cadvisor
# At this points it's prudent to wait 2 minute and ensure the elasticsearch cluster is up and running by checking port 9200.
docker-compose up -d apel
```

8. You should see data in the accounting dashboard within 24 hours.
