

build:
	docker build -t deltachat/pymailserver docker-mailserver/

push:
	docker push deltachat/pymailserver

shell:
	docker run -v `pwd`/..:/mnt -w /mnt --rm -it deltachat/pymailserver
