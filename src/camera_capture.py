import os
import time
import datetime
import threading
import queue
import re

import cv2

from .usb_camera import UsbCamera


class FrameQueue:
    def __init__(self, maxsize=1):
        self.q = queue.Queue(maxsize=maxsize)

    def put_latest(self, item):
        try:
            if self.q.full():
                _ = self.q.get_nowait()
            self.q.put_nowait(item)
        except queue.Empty:
            pass
        except queue.Full:
            pass

    def get_latest(self):
        try:
            return self.q.get_nowait()
        except queue.Empty:
            return None

    def clear(self):
        while True:
            try:
                self.q.get_nowait()
            except queue.Empty:
                return


class CaptureThread(threading.Thread):
    def __init__(
        self,
        camera: UsbCamera,
        frame_queue: FrameQueue,
        stop_event: threading.Event,
        save_event: threading.Event,
        target_fps: int = 30,
        output_dir: str = None,
        save_num: int = 1,
        debug: bool = False,
    ):
        super().__init__(daemon=True)
        self.camera = camera
        self.frame_queue = frame_queue
        self.stop_event = stop_event
        self.save_event = save_event
        self.lock = threading.Lock()

        # capture params
        self.interval = 1.0 / max(target_fps, 1)
        self.save_num = save_num
        self.save_cnt = 0

        # save images
        self.root_dir = output_dir
        self.output_dir = None
        self.error_message = None

        # debug
        self.debug = debug
        if self.debug:
            self._time0 = time.time()

    def _folder_safe_id(self, save_id):
        save_id = save_id.strip()
        return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", save_id)

    def _stop_with_error(self, message):
        self.error_message = message
        self.camera.is_opened = False
        self.stop_event.set()
        self.save_event.clear()

    def run(self):
        next_time = time.perf_counter()
        while not self.stop_event.is_set():
            next_time += self.interval

            if self.debug:
                print(f"Time: {time.perf_counter() - self._time0}")
                self._time0 = time.perf_counter()

            try:
                with self.lock:
                    frame = self.camera.capture()
            except cv2.error as err:
                self._stop_with_error(f"camera capture failed: {err}")
                break
            except OSError as err:
                self._stop_with_error(f"camera disconnected: {err}")
                break
            except Exception as err:
                self._stop_with_error(f"unexpected capture error: {err}")
                break

            if frame is None:
                self._stop_with_error("camera returned no frame")
                break

            self.frame_queue.put_latest(frame)

            # save image
            if self.save_event.is_set() and self.output_dir is not None:
                with self.lock:
                    save_path = f"{self.output_dir}/{self.save_cnt:04d}.jpg"
                    self.save_cnt += 1

                cv2.imwrite(save_path, frame)

            # if capture_num <=0, no limitation
            if self.save_num <= 0:
                pass
            elif self.save_cnt >= self.save_num:
                self.stop_save()

            # FPS調整
            wait = next_time - time.perf_counter() - 0.002  # 少し余裕を持たせる
            if wait > 0:
                time.sleep(wait)

    def start_save(self, save_id=""):
        if self.root_dir is None:
            return

        with self.lock:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_id = self._folder_safe_id(save_id)
            folder_name = f"{timestamp}_{safe_id}" if safe_id else timestamp
            self.output_dir = os.path.join(self.root_dir, folder_name)
            os.makedirs(self.output_dir, exist_ok=True)

            self.save_cnt = 0
            self.save_event.set()

    def stop_save(self):
        with self.lock:
            self.save_event.clear()
