import time
import requests
import traceback
from concurrent.futures import ThreadPoolExecutor

def run(input_uri):
    st = time.time()
    try:
        res = requests.post(f'http://localhost:8001/get_rtsp_status', json={'rtsp':f"{input_uri}"})
        print(f"{res.json()}")
        print(res.status_code)
    except Exception as ex:
        print.warning(f"Failed to check RTSP stream of camera with error: {ex}\n{traceback.format_exc()}")
    print.info(f"RTSP checking server response time: {time.time() - st}")

if __name__ == "__main__":
    uri = "rtsp://admin:Techainer123@techainer-hikvision-office-2.localdomain:554/media/video1"
    num_jobs = 4
    all_time = 0
    st = time.time()
    with ThreadPoolExecutor(max_workers=4) as executor:
        for _ in range(num_jobs):
            future = executor.submit(run, uri)
    
    print(f"Actual time: {time.time() - st} seconds")