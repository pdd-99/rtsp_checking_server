# syntax=docker/dockerfile:experimental
FROM python:3.8.13-slim-buster

RUN apt-get update && apt-get install -y ffmpeg && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN pip install -r /app/requirements.txt --no-cache-dir

COPY src /app/src

WORKDIR /app

CMD gunicorn --bind 0.0.0.0:8001 --timeout 0 src.rtsp_checking_server:app