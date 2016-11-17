import configparser, json, boto3, botocore
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


@app.route('/instances/<regex("i\-[a-z0-9]{8}"):instance_id>', methods=['GET'])
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

    json_response = json.dumps(instance, default=json_util.default, indent=4, sort_keys=True)
    return Response(json_response, mimetype='application/json')


@app.route('/spot_instance_requests', methods=['POST'])
def create_spot_request():
    print('\nCreating spot instance request...')

    instance_type       = config['AWS']['INSTANCE_TYPE']
    availability_zone   = config['AWS']['REGION_NAME'] + "b"
    spot_price          = config['AWS']['SPOT_PRICE']

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
    
    json_response = json.dumps(req['SpotInstanceRequests'][0], default=json_util.default, indent=4, sort_keys=True)
    return Response(json_response, mimetype='application/json')

@app.route('/spot_instance_requests', methods=['GET'])
def list_all_spot_requests():
    req = ec2_client.describe_spot_instance_requests()
    json_response = json.dumps(req['SpotInstanceRequests'], default=json_util.default, indent=4, sort_keys=True)
    return Response(json_response, mimetype='application/json')

@app.route('/spot_instance_requests/<regex("sir\-[a-z0-9]{8}"):request_id>', methods=['GET'])
def spot_request_status(request_id):
    req = ec2_client.describe_spot_instance_requests(
        SpotInstanceRequestIds=[
            request_id,
        ])
    filtered_fields = ["SpotInstanceRequestId", "State", "Status", "InstanceId"]
    to_filter_dict = req['SpotInstanceRequests'][0]
    request_state = filter_dict_fields(filtered_fields, to_filter_dict)
    json_response = json.dumps(request_state, default=json_util.default, indent=4, sort_keys=True)
    return Response(json_response, mimetype='application/json')


@app.route('/spot_instance_requests/<regex("sir\-[a-z0-9]{8}"):request_id>', methods=['DELETE'])
def spot_request_delete(request_id):
    req = ec2_client.cancel_spot_instance_requests(SpotInstanceRequestIds=[request_id])

    filtered_fields = ["SpotInstanceRequestId", "State"]
    to_filter_dict = req['CancelledSpotInstanceRequests'][0]
    request_state = filter_dict_fields(filtered_fields, to_filter_dict)
    json_response = json.dumps(request_state, default=json_util.default, indent=4, sort_keys=True)
    return Response(json_response, mimetype='application/json')


def filter_dict_fields(filtered_fields, to_filter_dict):
    filtered_dict = {k: v for k, v in to_filter_dict.items() if k in filtered_fields}
    return filtered_dict


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

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)

