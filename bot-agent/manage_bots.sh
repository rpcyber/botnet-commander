#!/bin/sh

if [ "$(id -u)" -ne 0 ]
then
	echo "Please run as root"
	exit
fi

comm=$1
START=$2
END=$3
docker=/usr/bin/docker

run () {
	for i in $(seq $START $END)
	do
		echo "Starting bot-agent nr $i"
		NAME=bot-agent-$i
		$docker container create -h $NAME --name $NAME bot-agent 
		$docker container start $NAME
	done
}

remove () {
	docker ps -a --filter "name=bot-agent-" --format '{{.ID}}'| xargs docker rm -f
}

case "$comm" in
	"start")
		run
		;;
	"remove")
		remove
		;;
	*)
		echo "Nothing to do"
		;;
esac
