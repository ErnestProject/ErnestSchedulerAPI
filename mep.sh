ssh ubuntu@52.57.135.219 << 'EOF'
set -x
docker_id=$(sudo docker ps | grep "bluep-tempo-api" | awk '{print $1}')
echo "docker_id" $docker_id
if [ ! -z "$docker_id" ]
then
   sudo docker stop $docker_id
   sudo docker rm $docker_id
fi

cd BluePTempoAPI

git pull -r

sudo docker build -t bluep-tempo-api:latest .
sudo docker run -d -p 80:5000 -v $(pwd):/app bluep-tempo-api
EOF