
.PHONY: full-build
full-build: pull build

.PHONY: pull
pull:
	docker pull gcc:9

.PHONY: build
build:
	docker build -t all-python .
