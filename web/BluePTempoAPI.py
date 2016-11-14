import configparser, json, boto3, string
import winrm
from bson import json_util
from flask import Flask, Response
from flask_cors import CORS, cross_origin
from werkzeug.routing import BaseConverter


config = configparser.ConfigParser()
config.read_file(open('conf/defaults.cfg'))
config.read('conf/secret.cfg')

app = Flask(__name__)
CORS(app)

if config.has_section('Auth') and config.has_option('Auth', 'AWSAccessKeyId') and config.has_option('Auth', 'AWSSecretKey'):
    session = boto3.Session(
        aws_access_key_id=config['Auth']['AWSAccessKeyId'],
        aws_secret_access_key=config['Auth']['AWSSecretKey'],
        region_name=config['AWS']['REGION_NAME']
    )
else:
    session = boto3.Session(
        region_name=config['AWS']['REGION_NAME']
    )

ec2_client = session.client('ec2')

class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]

app.url_map.converters['regex'] = RegexConverter



@app.route('/')
def version():
    return config['Global']['version']

@app.route('/instances', methods=['GET'])
def list_all_instances():
    print('Finding instance by AMI ID...')
    req = ec2_client.describe_instances(Filters=[
        {
            'Name': 'image-id',
            'Values': [ config['AWS']['GAMING_AMI_ID'] ]
        },
    ])
    
    def extract_instance(rawData):
        return rawData['Instances'][0]

    json_response = json.dumps(list(map(extract_instance, req['Reservations'])), default=json_util.default, indent=4, sort_keys=True)
    return Response(json_response, mimetype='application/json')

@app.route('/instances', methods=['POST'])
def create_instance():
    print('Creating spot instance request...')
    req = ec2_client.request_spot_instances(
        SpotPrice=config['AWS']['SPOT_PRICE'],
        InstanceCount=1,
        LaunchSpecification={
            'ImageId': config['AWS']['GAMING_AMI_ID'],
                'SecurityGroups': [config['AWS']['SECURITY_GROUP']],
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

@app.route('/instances/<regex("([0-9]{1,3}\.){3}[0-9]{1,3}"):instance_ip>', methods=['DELETE'])
def terminate_instance(instance_ip):
    print('Finding instance by IP...')
    req = ec2_client.describe_instances(Filters=[
        {
            'Name': 'ip-address',
            'Values': [
                instance_ip,
            ]
        },
    ])
    instance_id = req['Reservations'][0]['Instances'][0]['InstanceId']
    print('instance_id: ' + instance_id)
    print('Terminate instance')
    ec2_client.terminate_instances(
        InstanceIds=[
            instance_id
        ]
    )
    return instance_id

@app.route('/instances/<regex("([0-9]{1,3}\.){3}[0-9]{1,3}"):instance_ip>/install/<regex("[0-9]+"):game_id>', methods=['PATCH'])
def install_game(instance_ip, game_id):
    print('install game')
    ps_script = string.Template("""
        Read-S3Object -BucketName bluepolo-games -Key ${gameId}.zip -File 'Z:\${gameId}.zip'

        $ZipPath = "Z:\${gameId}.zip"
        $zipfile = (new-object -com shell.application).NameSpace($ZipPath)
        md "Z:\yop"
        $destinationPath = "Z:\yop"
        $destination = (new-object -com shell.application).NameSpace($destinationPath)
        $destination.CopyHere($zipfile.Items())
    """).safe_substitute(gameId=game_id)
    s = winrm.Session(instance_ip, auth=('Administrator', 'Polaroide000'))
    r = s.run_ps(ps_script)
    print(r.status_code, flush=True)
    print(r.std_out, flush=True)
    print(r.std_err, flush=True)

    return "OK"

@app.route('/titi', methods=['GET'])
def titi():
    print('install game')
    ps_script = """
        for($i=1; $i -le 10; $i++){tscon.exe $i /dest:console}
    """
    s = winrm.Session("35.156.11.120", auth=('Administrator', 'Polaroide000'))
    r = s.run_ps(ps_script)
    print(r.status_code, flush=True)
    print(r.std_out, flush=True)
    print(r.std_err, flush=True)

    return "OK"

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)

