#!/bin/bash

# Stop all dockers images
docker stop $(docker ps -a -q)

# Remove all exited images
docker rm $(docker ps -q -f status=exited)

# Build API
docker build -t bluep-tempo-api:latest . 

# Run the new image
docker run -d -p 5000:5000 bluep-tempo-api

# Watch logs
docker logs -f $(docker ps -q)