import json
import subprocess as sp
import time
from typing import Dict, Tuple

from loguru import logger
from omegaconf import OmegaConf


def get_ffprobe_path() -> str:
    cmd = f"which ffprobe"
    _process = sp.Popen(cmd, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
    msg = _process.communicate()[0].decode("utf-8").replace("\n","")
    if msg == "":
        raise Exception("Not found ffprobe. Please install it first.")
    return msg

def get_timeout_path() -> str:
    cmd = f"which timeout"
    _process = sp.Popen(cmd, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
    msg = _process.communicate()[0].decode("utf-8").replace("\n","")
    if msg == "":
        raise Exception("Not found timeout. Please install it first.")
    return msg

FFPROBE_PATH = get_ffprobe_path()
TIMEOUT_PATH = get_timeout_path()

def get_stream_metadata(input_uri: str, stream_checking_timeout: int = 5) -> Dict:
    command = f"{TIMEOUT_PATH} {stream_checking_timeout} {FFPROBE_PATH} -v quiet -print_format json -show_streams {input_uri} || if [ $? -eq 124 ]; then >&2 echo timeout; fi"
    stream_meta = sp.getoutput(command)
    if stream_meta == 'timeout':
        raise Exception("Timeout when checking stream url.")
    return json.loads(stream_meta)

def get_stream_url_status(stream_url, stream_checking_timeout: int = 5) -> Tuple[str, int]:
    cmd = f"{TIMEOUT_PATH} {stream_checking_timeout} {FFPROBE_PATH} -v error -select_streams v:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 -rtsp_transport tcp {stream_url} || if [ $? -eq 124 ]; then >&2 echo timeout; fi"
    _process = sp.Popen(cmd, shell=True, stdout=sp.PIPE, stderr=sp.PIPE, close_fds=True, bufsize=-1)
    msg = _process.communicate()

    if msg[0].decode("utf-8") != "":
        return "", 0
    else:
        msg = msg[1].decode("utf-8")
        if "refused" in msg.lower():
            status_message = f"CONNECTION REFUSED WHEN TRYING TO CONNECT TO {stream_url} FOR {stream_checking_timeout} SECONDS"
            status = 1
        elif "timeout" in msg.lower():
            status_message = f"TIMEOUT ERROR WHEN TRYING TO CONNECT TO {stream_url} FOR {stream_checking_timeout} SECONDS"
            status = 1
        elif msg.lower() == "":
            status_message = ""
            status = 0
        else:
            status_message = f"UNKNOWN ERROR WHEN TRYING TO CONNECT TO {stream_url} FOR {stream_checking_timeout} SECONDS"
            status = 1
    return status_message, status

def not_supported_type(value) -> bool:
    if isinstance(value, int):
        return False
    elif isinstance(value, str):
        return False
    elif isinstance(value, float):
        return False
    elif isinstance(value, bool):
        return False
    return True

def create_identical_env_config_with_default_config(file_cfg):
    """
    This will not support multi level config for now
    """
    res = {}
    expected_type = {}
    for key in file_cfg.keys():
        value = file_cfg[key]
        if not_supported_type(value):
            raise Exception(f"Unsupported type {type(value)} in config file")
        expected_type[key] = type(value)
        res[key] = f"${{oc.env:{key}, ???}}"
    return OmegaConf.create(json.dumps(res)), expected_type

def force_type(cfg, expected_type):
    for key in cfg.keys():
        try:
            if expected_type[key] == int:
                cfg[key] = int(cfg[key])
            elif expected_type[key] == float:
                cfg[key] = float(cfg[key])
            elif expected_type[key] == bool:
                cfg[key] = True if str(cfg[key]).strip().lower() in ['true', 't', 'yes', '1'] else False
            elif expected_type[key] == str:
                cfg[key] = str(cfg[key])
        except ValueError as e:
            logger.error(f"Error when convert type of `{key}` to `{expected_type[key]}` with expception:")
            raise e
    return cfg

def load_config(file_path: str):
    """
    Load config from yaml file, while being able to use env variable
    to override any config value with type annotation
    """
    default_cfg = OmegaConf.load(file_path)
    env_cfg, expected_type = create_identical_env_config_with_default_config(default_cfg)
    OmegaConf.resolve(env_cfg)
    cfg = OmegaConf.merge(default_cfg, env_cfg, OmegaConf.from_cli())
    cfg = force_type(cfg, expected_type)
    return cfg
