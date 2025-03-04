#!/bin/bash
export $(grep -v '^#' api.env | xargs)
source venv/bin/activate
PYTHONPATH=$(pwd) python src/main.py