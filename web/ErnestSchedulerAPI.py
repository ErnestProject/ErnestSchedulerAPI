import os, configparser, json, boto3, botocore
from bson import json_util
from flask import Flask, Response, request
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

def format_response(data):
    json_response = json.dumps(data, default=json_util.default, indent=4, sort_keys=True)
    return Response(json_response, mimetype='application/json')

def filter_dict_fields(filtered_fields, to_filter_dict):
    filtered_dict = {k: v for k, v in to_filter_dict.items() if k in filtered_fields}
    return filtered_dict


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

    return format_response(list(map(extract_instance, req['Reservations'])))


@app.route('/instances/<regex("i\-[a-z0-9]{17}"):instance_id>', methods=['GET'])
def describe_instance(instance_id):
    print('Finding instance by AMI ID...')
    req = ec2_client.describe_instances(
        InstanceIds=[
            instance_id,
        ],
        Filters=[
        {
            'Name': 'image-id',
            'Values': [ config['AWS']['GAMING_AMI_ID'] ]
        },
    ])

    filtered_fields = ["InstanceId", "State", "PublicIpAddress"]
    to_filter_dict = req['Reservations'][0]['Instances'][0]
    instance = filter_dict_fields(filtered_fields, to_filter_dict)

    return format_response(instance)


@app.route('/spot_instance_requests', methods=['POST'])
def create_spot_request():
    print('\nCreating spot instance request...')

    instance_type       = config['AWS']['INSTANCE_TYPE']
    availability_zone   = config['AWS']['AVAILABILITY_ZONE']
    spot_price          = config['AWS']['SPOT_PRICE']

    if request.data:
        post_params = json.loads(request.data.decode("utf-8"))
        if 'type' in post_params and post_params['type']:
            instance_type       = post_params['type']
        if 'location' in post_params and post_params['location']:
            availability_zone   = post_params['location']
        if 'price' in post_params and post_params['price']:
            spot_price          = str(post_params['price'])

    print(instance_type, availability_zone, spot_price)

    req = ec2_client.request_spot_instances(
        SpotPrice=spot_price,
        InstanceCount=1,
        LaunchSpecification={
            'ImageId': config['AWS']['GAMING_AMI_ID'],
            'SecurityGroups': [config['AWS']['SECURITY_GROUP']],
            'InstanceType': instance_type,
            'Placement': {
                'AvailabilityZone': availability_zone,
            },
            'IamInstanceProfile': {
                'Name': 'game-installer',
            }

        }
    )

    return format_response(req['SpotInstanceRequests'][0])

@app.route('/spot_instance_requests', methods=['GET'])
def list_all_spot_requests():
    req = ec2_client.describe_spot_instance_requests()
    return format_response(req['SpotInstanceRequests'])

@app.route('/spot_instance_requests/<regex("sir\-[a-z0-9]{8}"):request_id>', methods=['GET'])
def spot_request_status(request_id):
    req = ec2_client.describe_spot_instance_requests(
        SpotInstanceRequestIds=[
            request_id,
        ])
    filtered_fields = ["SpotInstanceRequestId", "State", "Status", "InstanceId"]
    to_filter_dict = req['SpotInstanceRequests'][0]
    request_state = filter_dict_fields(filtered_fields, to_filter_dict)

    return format_response(request_state)

@app.route('/spot_instance_requests/<regex("sir\-[a-z0-9]{8}"):request_id>', methods=['DELETE'])
def spot_request_delete(request_id):
    req = ec2_client.cancel_spot_instance_requests(SpotInstanceRequestIds=[request_id])

    filtered_fields = ["SpotInstanceRequestId", "State"]
    to_filter_dict = req['CancelledSpotInstanceRequests'][0]
    request_state = filter_dict_fields(filtered_fields, to_filter_dict)
    return format_response(request_state)

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

    return format_response(instance_id)






@app.route('/instances/<regex("([0-9]{1,3}\.){3}[0-9]{1,3}"):instance_ip>/actions', methods=['GET'])
def get_instance_actions(instance_ip):
    print('Gettings actions from instance ' + instance_ip + '...')

    fileName = 'instances_commands/stack_' + instance_ip + '.command'
    if (not os.path.exists(fileName)):
        return format_response("no_pending_command")

    try:
        file = open(fileName, 'r')
        result = file.read()
        file.close()

        if 'take' in request.args and request.args['take'] in ['true', '1', 'y', 'yes', 'sir_yes_sir']:
            file = open(fileName, 'w')
            file.close()

        if result:
            return format_response(result)
        else:
            return format_response("no_pending_command")
    except Exception as e:
        raise e

    return format_response(False)

@app.route('/instances/<regex("([0-9]{1,3}\.){3}[0-9]{1,3}"):instance_ip>/actions', methods=['POST'])
def send_instance_action(instance_ip):
    print('Sending command to instance ' + instance_ip + '...')
    post_params = json.loads(request.data.decode("utf-8"))

    if 'action' not in post_params or not post_params['action']:
        return Response("Error: Missing action", mimetype='application/json')
    if 'params' not in post_params:
        return Response("Error: Missing params", mimetype='application/json')

    if (not os.path.exists('instances_commands')):
        os.makedirs('instances_commands')

    try:
        file = open('instances_commands/stack_' + instance_ip + '.command', 'w')

        if (not post_params['params']):
            file.write(post_params['action'])
        else:
            file.write(post_params['action'] + '>>>' + '%%'.join(post_params['params']))

        file.close()
    except Exception as e:
        raise e
    
    return format_response(True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)

