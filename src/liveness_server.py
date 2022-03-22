import os

os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"

import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from multiprocessing import Process
from threading import Thread

import GPUtil
import zmq
from loguru import logger

from .utils import load_config


class LivenessHandler(BaseHTTPRequestHandler):
    def __init__(self,
                liveness_mode: int = 0,
                zmq_port: int = 5555,
                zmq_recv_timeout: float = 0.1,
                gpu_util_threshold: int = 1,
                gpu_vram_threshold: int = 90,
                gpu_util_max_duration: int = 5,
                gpu_vram_max_duration: int = 5,
                zmq_no_msg_max_duration: int = 5,
                ):
        self.liveness_mode = liveness_mode
        self.zmq_port = zmq_port
        self.zmq_recv_timeout = zmq_recv_timeout
        self.gpu_util_threshold = gpu_util_threshold
        self.gpu_vram_threshold = gpu_vram_threshold
        self.gpu_util_max_duration = gpu_util_max_duration
        self.gpu_vram_max_duration = gpu_vram_max_duration
        self.zmq_no_msg_max_duration = zmq_no_msg_max_duration
        self.host = "0.0.0.0"
        self.liveness = 200, "All good"
        self.main_thread = Thread(target=self.process_zmq_msg)
        self.main_thread.start()

    def __call__(self, *args, **kwargs):
        """Handle a request."""
        super().__init__(*args, **kwargs)

    def do_GET(self):
        status, msg = self.liveness
        self.send_response(status)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(bytes(f"{msg}", "utf-8"))

    def process_zmq_msg(self):
        # Creates a socket instance
        context = zmq.Context()
        socket = context.socket(zmq.SUB)

        # Connects to a bound socket
        socket.connect("tcp://{}:{}".format(self.host, self.zmq_port))

        # Subscribes to all topics
        socket.subscribe("")

        # Config zmq recv timeout
        socket.RCVTIMEO = int(self.zmq_recv_timeout*1000)

        # Init elapsed time
        gpu_util_elapsed_time = 0
        gpu_vram_elapsed_time = 0
        zmq_message_elapsed_time = 0

        # Init counter
        msg_counter = 0

        # GPUtil sometimes failed, should retry
        gputil_max_retry = 10

        last_msg_receiving_time = None
        # t_probe = time.time()

        if self.liveness_mode == 4:
            self.liveness = 400, "Dummy error"
            return

        if self.liveness_mode == 5:
            self.liveness = 200, "Dummy good"
            return

        while True:
            try:
                if last_msg_receiving_time is None:
                    msg_receiving_time = 0
                else:
                    msg_receiving_time = time.time() - last_msg_receiving_time # in seconds
                msg = socket.recv_string()
                last_msg_receiving_time = time.time()
                zmq_message_elapsed_time = 0 # reset zmq_message_elapsed_time if msg is received
            except zmq.ZMQError:
                zmq_message_elapsed_time += self.zmq_recv_timeout
                if zmq_message_elapsed_time > self.zmq_no_msg_max_duration and (self.liveness_mode == 0 or self.liveness_mode == 1):
                    self.liveness = 400, f"No message received for more than {self.zmq_no_msg_max_duration} seconds."
                else:
                    time.sleep(1/10000)
                    continue
            
            # The whole process below took more than 10 ms
            for _ in range(gputil_max_retry):
                try:
                    current_gpu = GPUtil.getGPUs()[0]
                    break
                except:
                    continue
            
            gpu_util = current_gpu.load*100 # in %
            gpu_vram = current_gpu.memoryUtil*100 # in %
            msg_counter += 1

            tokens = msg.split('-')
            num_cameras = int(tokens[0].split(":")[1].strip())
            
            if num_cameras > 0:
                if gpu_util < self.gpu_util_threshold:
                    gpu_util_elapsed_time += msg_receiving_time
                else:
                    gpu_util_elapsed_time = 0

                if gpu_vram > self.gpu_vram_threshold:
                    gpu_vram_elapsed_time += msg_receiving_time
                else:
                    gpu_vram_elapsed_time = 0
            
            if gpu_util_elapsed_time > self.gpu_util_max_duration and (self.liveness_mode == 0 or self.liveness_mode == 2):
                self.liveness = 400, f"Camera is still available but current GPU utilization {gpu_util}% is too low. Monitored for {gpu_util_elapsed_time}s"
            
            if gpu_vram_elapsed_time > self.gpu_vram_max_duration and (self.liveness_mode == 0 or self.liveness_mode == 3):
                self.liveness = 400, f"Camera is using too much GPU, current {gpu_vram}% is too high. Monitored for {gpu_vram_elapsed_time}s"


class LivenessServer:
    def __init__(self,
                liveness_mode: int = 0,
                liveness_server_port: int = 5555,
                zmq_port: int = 5555,
                zmq_recv_timeout: float = 0.1,
                gpu_util_threshold: int = 1,
                gpu_vram_threshold: int = 90,
                gpu_util_max_duration: int = 5,
                gpu_vram_max_duration: int = 5,
                zmq_no_msg_max_duration: int = 5,
            ):

        self.handler = LivenessHandler(
                liveness_mode,
                zmq_port,
                zmq_recv_timeout,
                gpu_util_threshold,
                gpu_vram_threshold,
                gpu_util_max_duration,
                gpu_vram_max_duration,
                zmq_no_msg_max_duration,
            )
        self.liveness_server_port = liveness_server_port
        self.main_process = Process(target=self.process)
    
    def start(self):
        self.main_process.start()

    def process(self):
        webServer = HTTPServer(("0.0.0.0", self.liveness_server_port), self.handler)
        webServer.serve_forever()

if __name__=="__main__":
    config = load_config('config.yaml')
    _liveness_server = LivenessServer(
        liveness_mode=int(config.liveness_mode),
        liveness_server_port=int(config.liveness_server_port),
        zmq_port=int(config.zmq_port),
        zmq_recv_timeout=float(config.zmq_recv_timeout),
        gpu_util_threshold=int(config.gpu_util_threshold),
        gpu_vram_threshold=int(config.gpu_vram_threshold),
        gpu_util_max_duration=int(config.gpu_util_max_duration),
        gpu_vram_max_duration=int(config.gpu_vram_max_duration),
        zmq_no_msg_max_duration=int(config.zmq_no_msg_max_duration),
    )
    _liveness_server.start()
    logger.warning("!!!!!!!!!!!!! Start liveness server !!!!!!!!!!!!!")
