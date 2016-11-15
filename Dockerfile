FROM ubuntu:latest
MAINTAINER Bastien Fiorentino "fiorentino.bastien@gmail.com"
ADD web/requirements.txt requirements.txt
RUN apt-get update -y && apt-get install -y python3.5 python3.5-dev build-essential curl && curl -SL 'https://bootstrap.pypa.io/get-pip.py' | python3.5 && pip install -r requirements.txt
WORKDIR /app
ENTRYPOINT ["python3.5"]
CMD ["web/ErnestSchedulerAPI.py"]
