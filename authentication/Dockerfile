FROM docker.io/library/python:3.13.1-alpine

WORKDIR /usr/src/app
RUN pip install --no-cache-dir Flask==3.1.0 PyJWT==2.10.1 
COPY authentication_server.py .
COPY templates ./templates

USER 10000
EXPOSE 8000
CMD ["python", "authentication_server.py"]
