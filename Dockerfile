FROM ubuntu:latest
MAINTAINER Bastien Fiorentino "fiorentino.bastien@gmail.com"
ADD web/requirements.txt requirements.txt
RUN apt-get update -y && apt-get install -y python3.5 python3.5-dev build-essential curl && curl -SL 'https://bootstrap.pypa.io/get-pip.py' | python3.5 && pip install -r requirements.txt
RUN apt-get install -y git && git clone https://github.com/BastienF/pywinrm.git && cd pywinrm && git checkout v0.2.1_stable && python3.5 setup.py install && cd .. && rm -r pywinrm
WORKDIR /app
ENTRYPOINT ["python3.5"]
CMD ["web/BluePTempoAPI.py"]
