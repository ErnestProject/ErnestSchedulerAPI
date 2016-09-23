import boto3
from flask import Flask

GAMMING_AMI_ID = 'ami-89f904e6'
SECURITY_GROUP = 'lg'
SPOT_PRICE = '0.50'

app = Flask(__name__)
session = boto3.Session(
#    aws_access_key_id="",
#    aws_secret_access_key="",
    region_name="eu-central-1"
)
ec2_client = session.client('ec2')

from werkzeug.routing import BaseConverter

class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]

app.url_map.converters['regex'] = RegexConverter

@app.route('/')
def version():
    return 'BluePTempoAPI v0.0.1'

@app.route('/create_instance')
def create_instance():
    print('Creating spot instance request...')
    req = ec2_client.request_spot_instances(
        SpotPrice=SPOT_PRICE,
        InstanceCount=1,
        LaunchSpecification={
            'ImageId': GAMMING_AMI_ID,
                'SecurityGroups': [SECURITY_GROUP],
            'InstanceType': 'g2.2xlarge',
            'Placement': {
                'AvailabilityZone': 'eu-central-1b',
            },
            'IamInstanceProfile': {
                'Name': 'game-installer',
            }

        }
    )
    req_id = req['SpotInstanceRequests'][0]['SpotInstanceRequestId']
    print('req_id: ' + req_id)

    print('Waiting for instance to be launched...')
    waiter = ec2_client.get_waiter('spot_instance_request_fulfilled')
    waiter.wait(SpotInstanceRequestIds=[req_id])
    req = ec2_client.describe_spot_instance_requests(SpotInstanceRequestIds=[req_id])
    instance_id = req['SpotInstanceRequests'][0]['InstanceId']
    print('instance_id: ' + instance_id)

    print('Removing the spot instance request...')
    ec2_client.cancel_spot_instance_requests(SpotInstanceRequestIds=[req_id])

    print('Getting ip address...')
    req = ec2_client.describe_instances(InstanceIds=[instance_id])
    instance_ip = req['Reservations'][0]['Instances'][0]['PublicIpAddress']
    print('instance_ip: ' + instance_ip)

    return instance_ip


if __name__ == '__main__':
    app.run(host='0.0.0.0')

