#!/bin/bash
export $(grep -v '^#' bot.env | xargs)
source venv/bin/activate
PYTHONPATH=$(pwd) python tg_bot/main.py