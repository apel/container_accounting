# container_accounting

The below documentation assumes deploying the entire system as docker containers. Other deployment methods (such as using non-containerized versions of the software) is theoretically possible, but not supported.

Running the container accounting collector involves running two containers.
1. cAdvisor 0.35.0
1. an APEL container

The APEL container:
* Periodically and frequently polls the cAdvisor API to "monitor" the running containers, storing one measurement per container per day in a remote elasticsearch.

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
docker-compose pull
```

3. Edit `conf/client.cfg`
  * set `site_name` to a meaningful, human readable, identifier for your site. This will be visible in the accounting dashboard.
  * set the elasticsearch url

4. Edit `docker-compose.yml` to suit your exact deployment
  * You'll need to replace `./conf/client.cfg` with the absolute path.

5. Run the two containers
```
docker-compose up -d cadvisor
docker-compose up -d apel
```

6. You should see data in the accounting dashboard within minutes.
