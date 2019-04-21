
build: Dockerfile
	docker build -t all-python . <Dockerfile

Dockerfile: bin/generate-dockerfile
	./bin/generate-dockerfile >Dockerfile

