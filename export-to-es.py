#!/usr/bin/python3
#
# export-to-es.py
#
# Export a Plex media database to Elasticsearch.
#
# Running directly:
# Requires: pipenv install -or- pip install elasticsearch
# Just supply the URL to your Elasticsearch install followed by the path to your Plex database file
#
# Ex. python3 export-to-es.py http://192.168.2.61:9200  /volume1/Plex/Library/Application Support/Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db
#
#
# Running from Docker:
# 1. Build your Docker image: docker build -t plex2es .
# 2. Create the container:
#      docker create --name plex2es \
#          -e ELASTICSEARCH=ip_of_elasticsearch:port \
#          -v /PATH/TO/com.plexapp.plugins.library.db:/plex.db:ro \
#          plex2es
#
# 3. Run with: docker start plex2es
#    The container will stop when the job is finished. Use docker logs -f plex2es to see log output.
#
# Two indexes are added: "movies" and "tvshows".  Each time this script is run the indexes are removed and rebuilt.
#
import sys
import os
import sqlite3
from math import floor

from elasticsearch import Elasticsearch

MOVIE_INDEX_NAME = 'plex_movies'
TV_INDEX_NAME = 'plex_tv'

movie_sql = [
    "select  items.id, sections.name, mdata.metadata_type, mdata.title, mdata.studio, mdata.content_rating, mdata.duration,",
    "        mdata.tags_genre, mdata.tags_director, mdata.tags_writer, mdata.originally_available_at,",
    "        mdata.tags_country, mdata.tags_star, mdata.year, mdata.duration,",
    "        items.width, items.height, items.container, items.video_codec, items.audio_codec",
    "from    library_sections as sections,",
    "        metadata_items as mdata,",
    "        media_items as items",
    "where   mdata.library_section_id = sections.id",
    "and     items.metadata_item_id = mdata.id",
    "and     mdata.metadata_type = '1'"
]


series_sql = [
    "select  mdata.id, sections.name, mdata.metadata_type, mdata.title, mdata.studio, mdata.content_rating,",
    "        mdata.tags_genre, mdata.originally_available_at ",
    "from    library_sections as sections,",
    "        metadata_items as mdata",
    "where   mdata.library_section_id = sections.id",
    "and     mdata.metadata_type = '2'"
]

sql_episodes_count = [
    "select count()",
    "from metadata_items mi",
    "inner join metadata_items season on season.parent_id = mi.id",
    "inner join metadata_items episode on episode.parent_id = season.id",
    "where mi.metadata_type = '2'",
    "and   mi.id=?"
]

sql_episodes = [
    'select episode."index", episode.title, episode.tags_director, episode.tags_writer',
    "from metadata_items mi",
    "inner join metadata_items season on season.parent_id = mi.id",
    "inner join metadata_items episode on episode.parent_id = season.id",
    "where mi.metadata_type = '2'",
    'and   season."index"=?'
    "and   mi.id=?"
]

season_counts = [
    'select season."index" as season, sum(media.duration) as duration, sum(media.size) as size',
    'from metadata_items mi, media_items media',
    'inner join metadata_items season on season.parent_id = mi.id',
    'inner join metadata_items episode on episode.parent_id = season.id',
    "where mi.metadata_type = '2'",
    'and mi.id = ?',
    'and media.metadata_item_id = episode.id',
    'and season."index" != 0',
    'group by season'
]


def export_movies(es: Elasticsearch, con: sqlite3.dbapi2):
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    print("creating movies...")
    s = ' '.join(movie_sql)
    if es.indices.exists(MOVIE_INDEX_NAME):
        es.indices.delete(MOVIE_INDEX_NAME)
    for row in cur.execute(s).fetchall():
        rec = dict(row)
        #print(rec['id'], rec['title'])
        rec['height'] = str(rec['height'])
        rec['width'] = str(rec['width'])
        rec['tags_director'] = rec['tags_director'].split('|')
        rec['tags_writer'] = rec['tags_writer'].split('|')
        rec['tags_star'] = rec['tags_star'].split('|')
        rec['tags_genre'] = rec['tags_genre'].split('|')
        if 'duration' in row and row['duration'] is not None:
            duration = floor(row['duration'] / 1000 / 60) / 60
            rec['duration'] = duration
        rec['year'] = str(rec['year'])
        es.create(MOVIE_INDEX_NAME, rec['id'], rec)


def export_tv(es: Elasticsearch, con: sqlite3.dbapi2):

    print("creating tv...")
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    s = ' '.join(series_sql)
    if es.indices.exists(TV_INDEX_NAME):
        es.indices.delete(TV_INDEX_NAME)
    for row in cur.execute(s).fetchall():
        rec = dict(row)
        mi = rec['id']
        count = cur.execute(' '.join(sql_episodes_count), (mi,)).fetchone()
        rec['episodes'] = int(count[0])
        rec['tags_genre'] = rec['tags_genre'].split('|')
        seasons = list()
        rec['seasons'] = seasons
        t_duration = 0
        t_size = 0
        for srec in cur.execute(' '.join(season_counts), (mi,)).fetchall():
            row = dict(srec)
            season = row['season']
            duration = floor(row['duration'] / 1000 / 60) / 60
            size = floor(row['size'] / 1000 / 1000)
            t_duration += duration
            t_size += size
            episodes = cur.execute(' '.join(sql_episodes), (season+1, mi)).fetchall()
            episodes = [dict(ep) for ep in episodes]
            for ep in episodes:
                ep['tags_writer'] = ep['tags_writer'].split('|')
                ep['tags_director'] = ep['tags_director'].split('|')
            seasons.append({'season': season, 'duration': duration, 'size': size, 'episodes': episodes})

        rec['total_duration'] = t_duration
        rec['total_size'] = t_size
        es.create(TV_INDEX_NAME, rec['id'], rec)


def in_docker():
    """ Returns: True if running in a Docker container, else False """
    with open('/proc/1/cgroup', 'rt') as ifh:
        cgroups = ifh.read()
        return 'docker' in cgroups or 'kube' in cgroups


if __name__ == '__main__':

    if in_docker():
        es_url = os.environ.get('ELASTICSEARCH', 'ElasticSearch URL Missing')
        plex_db = '/data' #/com.plexapp.plugins.library.db'
    else:
        es_url = sys.argv[1]
        plex_db = sys.argv[2]

    es = Elasticsearch([es_url])
    con = sqlite3.connect(plex_db)
    export_movies(es, con)
    export_tv(es, con)
    print("done.")
