
full-build: pull build

pull:
	docker pull buildpack-deps

build: Dockerfile
	docker build -t all-python . <Dockerfile

Dockerfile: bin/generate-dockerfile
	./bin/generate-dockerfile >Dockerfile

