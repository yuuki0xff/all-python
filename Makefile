
.PHONY: full-build
full-build: pull build

.PHONY: pull
pull:
	docker pull buildpack-deps

.PHONY: build
build: Dockerfile
	docker build -t all-python .

Dockerfile: bin/generate-dockerfile
	./bin/generate-dockerfile >Dockerfile

