1. docker build -t bluep-tempo-api:latest .
2. docker run -d -p 5000:5000 -v $(pwd):/app bluep-tempo-api
3. curl localhost:5000
4. docker stop $(docker ps -a -q)