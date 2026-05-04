DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
FILE := $(DIR)tia_parallel.py

.PHONY: all format check test

all: format check test

format:
	ruff format --line-length 180 $(FILE)

check:
	ruff check $(FILE) && env -u VIRTUAL_ENV ty check $(FILE)

test:
	cd $(DIR) && pytest -v tia_parallel.py
