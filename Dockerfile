FROM ubuntu:latest
MAINTAINER Bastien Fiorentino "fiorentino.bastien@gmail.com"
RUN apt-get update -y
RUN apt-get install -y python3.5 python3.5-dev build-essential curl
RUN curl -SL 'https://bootstrap.pypa.io/get-pip.py' | python3.5
COPY . /app
WORKDIR /app
RUN pip install -r web/requirements.txt
ENTRYPOINT ["python3.5"]
CMD ["web/BluePTempoAPI.py"]