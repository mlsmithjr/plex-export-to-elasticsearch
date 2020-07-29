## plex-export-to-elasticsearch
Script/container to load media information from Plex database into Elasticsearch

This script provides an easy way to get your Plex metadata into Elasticsearch so you can build
cool dashboards with Kibana or other tool of choice.  It will only **read** from your database - it will never change it.

## Running directly
 Requires: `pipenv install -or- pip install elasticsearch`
 
 Just supply the URL to your Elasticsearch install followed by the path to your Plex database file

Example:
```bash
python3 export-to-es.py http://192.168.2.61:9200  /volume1/Plex/Library/Application Support/Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db
```

## Running from Docker:
 1. Build your Docker image: `docker build -t plex2es .`
 2. Create the container:
 ```bash
      docker create --name plex2es \
          -e ELASTICSEARCH=ip_of_elasticsearch:port \
          -v /PATH/TO/com.plexapp.plugins.library.db:/plex.db:ro \
          plex2es
```
 3. Run with: `docker run plex2es`
    The container will stop when the job is finished. Use `docker logs -f plex2es` to see log output.

 Two indexes are added: "plex_movies" and "plex_tv".  Each time this script is run the indexes are removed and rebuilt.

## Setting up Elasticsearch and Kibana
If you are starting from scratch without an existing Elasticsearch or Kibana container
you can use this docker-compose file to quickly get started. Customize as you like.
This may even be installed along side existing elastic or kibana containers since these
will share a custom network.  As long as the names don't conflict the containers will only see
each other.

```yaml
version: '2.2'
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.6.2
    container_name: es01
    environment:
      - discovery.type=single-node
      - bootstrap.memory_lock=true
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    ulimits:
      memlock:
        soft: -1
        hard: -1
    volumes:
      - YOUR_ES_DATA_DIR:/usr/share/elasticsearch/data
    ports:
      - 9200:9200
    networks:
      - esnet

  kib01:
    image: docker.elastic.co/kibana/kibana:7.6.2
    container_name: kib01
    ports:
      - 5601:5601
    environment:
      ELASTICSEARCH_URL: http://es01:9200
      ELASTICSEARCH_HOSTS: http://es01:9200
    networks:
      - esnet
     
networks:
  esnet:
    driver: bridge
```

