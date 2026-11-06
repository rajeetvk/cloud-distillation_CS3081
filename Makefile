PYTHON ?= python

.PHONY: all train up down test lint

all: train

train:
ifdef SUBSET
	$(PYTHON) training/train.py --subset $(SUBSET)
else
	$(PYTHON) training/train.py
endif

up:
	k3d cluster create cloud-cluster --config cluster/k3d.yaml || true
	kubectl apply -f cluster/seaweedfs.yaml
	kubectl wait --namespace data --for=condition=ready pod -l app=seaweedfs --timeout=90s
	kubectl apply -f cluster/app.yaml || true

down:
	k3d cluster delete cloud-cluster || true

lint:
	flake8 service training worker tools || true

test:
	$(PYTHON) -m unittest discover -s tests -p "test_*.py"
