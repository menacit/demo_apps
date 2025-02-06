FROM docker.io/library/python:3.13.1-alpine

WORKDIR /usr/src/app
RUN pip install --no-cache-dir Flask==3.1.0 requests==2.32.3
COPY analytics_server.py .

EXPOSE 1338
CMD ["python", "analytics_server.py"]
