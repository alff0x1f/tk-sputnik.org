PODMAN   ?= docker
REGISTRY ?= registry.lab.tk-sputnik.org
IMAGE    ?= sputnik
TAG      ?= latest

FULL_IMAGE = $(REGISTRY)/$(IMAGE):$(TAG)

.PHONY: build push build-push login

build:
	$(PODMAN) build -t $(FULL_IMAGE) --platform linux/amd64 .

push:
	$(PODMAN) push $(FULL_IMAGE)

build-push: build push

login:
	$(PODMAN) login $(REGISTRY)
