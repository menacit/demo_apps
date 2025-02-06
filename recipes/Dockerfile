FROM docker.io/library/python:3.13.1-alpine

RUN apk --no-cache add figlet

WORKDIR /usr/src/app
RUN pip install --no-cache-dir Flask==3.1.0 requests==2.32.3
COPY recipes_server.py .

USER 10000
EXPOSE 1338
CMD ["python", "recipes_server.py"]
