FROM python:3.7-alpine3.9

RUN mkdir /app
COPY export-to-es.py requirements.txt /app/
RUN pip3 install -r /app/requirements.txt && chmod 777 /app/export-to-es.py
VOLUME /data

ENTRYPOINT ["/usr/local/bin/python3", "/app/export-to-es.py"]
