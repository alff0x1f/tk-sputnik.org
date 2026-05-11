PODMAN   ?= docker
REGISTRY ?= registry.lab.tk-sputnik.org
IMAGE    ?= sputnik
TAG      ?= latest

FULL_IMAGE = $(REGISTRY)/$(IMAGE):$(TAG)

.PHONY: build push build-push login lint format test

build:
	$(PODMAN) build -t $(FULL_IMAGE) --platform linux/amd64 .

push:
	$(PODMAN) push $(FULL_IMAGE)

build-push: build push

login:
	$(PODMAN) login $(REGISTRY)

lint:
	uv run ruff check .

format:
	uv run ruff format .

test:
	uv run pytest
