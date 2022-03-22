import json
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Dict
from threading import Thread

from flask import Flask, Response, request
from loguru import logger

from .utils import get_stream_url_status

app = Flask(__name__)
RTSP_STATUS_DICT = {}
INTERVAL = 2
STREAM_CHECKING_TIMEOUT = 5
MAX_WORKERS = 4

def rtsp_checking(stream_url):
    status_message, status =  get_stream_url_status(stream_url)
    RTSP_STATUS_DICT[stream_url].appendleft((status_message, status))

def rtsp_checking_thread():
    while True:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for stream_url in RTSP_STATUS_DICT.keys():
                executor.submit(rtsp_checking, stream_url)

RTSP_CHECKING_THREAD = Thread(target=rtsp_checking_thread)
RTSP_CHECKING_THREAD.start()

@app.route('/get_rtsp_status', methods=['POST'])
def get_rtsp_status():
    global RTSP_STATUS_DICT
    uri = request.json['rtsp']
    if uri not in RTSP_STATUS_DICT.keys():
        RTSP_STATUS_DICT[uri] = deque()

    try:
        status_message, status = RTSP_STATUS_DICT[uri].pop()
    except Exception as e:
        status_message = f"Status of {uri} is N/A for now. Don't worry, we will check it again in {INTERVAL} seconds."
        status = 200
        logger.warning(status_message)

    return Response(response=json.dumps({"msg": status_message, "status": status}), mimetype='application/json')

@app.route('/remove_rtsp_uri', methods=['POST'])
def remove_rtsp_uri():
    global RTSP_STATUS_DICT
    uri = request.json['rtsp']
    if uri in RTSP_STATUS_DICT.keys():
        RTSP_STATUS_DICT.pop(uri)
        msg = "OK"
    else:
        msg = "RTSP NOT FOUND"
    return Response(response=json.dumps({"msg": f"{msg}", "status": 200}), mimetype='application/json')