import glob
import os
import shutil
import sys
import time
import datetime
import threading
import queue
from typing import List, Optional, Tuple

import cv2
import tkinter
from tkinter import ttk, messagebox, simpledialog, filedialog

from image_info import ImageData
from canvas import Canvas
from usb_camera import UsbCamera


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


class CaptureThread(threading.Thread):
    def __init__(self, camera: UsbCamera,
                 frame_queue: FrameQueue,
                 stop_event: threading.Event,
                 save_event: threading.Event,
                 target_fps: int = 30,
                 output_dir: str = None,
                 save_num: int = 1):
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

        # debug
        self.debug = True
        if self.debug:
            self._time0 = time.time()

    def run(self):

        while not self.stop_event.is_set():
            t0 = time.time()

            if self.debug:
                print(f"Time: {time.time() - self._time0}")
                self._time0 = time.time()

            frame = self.camera.capture()
            if frame is not None:
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
            dt = time.time() - t0
            sleep_time = self.interval - dt
            if sleep_time > 0:
                time.sleep(sleep_time * 0.7)

    def start_save(self):
        if self.root_dir is None:
            return

        with self.lock:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_dir = os.path.join(self.root_dir, timestamp)
            os.makedirs(self.output_dir, exist_ok=True)

            self.save_cnt = 0
            self.save_event.set()

    def stop_save(self):
        with self.lock:
            self.save_event.clear()


class CameraViewer:
    def __init__(self, camera_no=0, cap_w=None, cap_h=None, cap_fps=None):
        self.root = tkinter.Tk()
        self.root.title('CameraViewer')
        self.root.geometry("1000x700")
        self.root.attributes('-topmost', True)
        self.root.protocol('WM_DELETE_WINDOW', self.close_window)

        # image params
        self.cvs: Optional[Canvas] = None

        # Camera
        self.camera_no = camera_no
        self.camera = UsbCamera(camera_no=camera_no)

        self.cap_h = cap_h
        self.cap_w = cap_w
        self.cap_fps = cap_fps

        self.stop_event = threading.Event()
        self.frame_queue = FrameQueue(maxsize=1)
        self.capture_thread = None

        # Save
        self.cwd = os.getcwd()
        self.out_dir = "./images"
        self.save_event = threading.Event()
        self.save_flg = False

        # Etc
        self.root.bind("<Configure>", self.resize_window)
        self._last_size = (0, 0)

        # frame-related
        self.root.update_idletasks()
        self.root_h = self.root.winfo_height()
        self.root_w = self.root.winfo_width()

        self.frame1 = None
        self.frame2 = None
        self.cvs_h = None
        self.cvs_w = None

        self.msg_status = tkinter.StringVar()
        self.msg_camera = tkinter.StringVar()
        self.msg_save = tkinter.StringVar()
        self.var_save = tkinter.StringVar(value="0")
        self.spin_capture = None

        # build UI
        self.set_frames()
        self.root.mainloop()

    def exit(self):
        # 終了処理
        try:
            self.stop_capture()  # stop_event set + save_event clear
            if self.capture_thread is not None:
                self.capture_thread.join(timeout=1.0)
        except Exception:
            pass

        try:
            self.close_camera()
        except Exception:
            pass

        self.root.destroy()

    def close_window(self):
        if messagebox.askokcancel("title", "close window?"):
            self.exit()

    # ---- UI build ---------------------------------------
    def set_frames(self):
        for child in self.root.winfo_children():
            child.destroy()

        # left: info/control
        self.frame1 = tkinter.Frame(self.root, width=300, height=self.root_h, borderwidth=10)
        self.frame1.pack(side='left', fill=tkinter.Y)

        # right: images
        self.frame2 = tkinter.Frame(self.root, width=1700, height=self.root_h, bg='#fffffa', borderwidth=10)
        self.frame2.pack(side='right', fill=tkinter.BOTH, expand=True)

        self.set_frame1()

        self.root.update_idletasks()
        f2_h = self.frame2.winfo_height()
        f2_w = self.frame2.winfo_width()
        self.cvs_h = int(f2_h * 0.95)
        self.cvs_w = int(f2_w * 0.95)
        self.set_frame2()

        self.set_menu()

    def set_frame1(self, frame_width=20):

        def _label(text=None, textvariable=None, pady=1, **kwargs):
            if text is not None:
                _lbl = tkinter.Label(self.frame1, text=text, width=frame_width, anchor=tkinter.W, **kwargs)
            elif textvariable is not None:
                _lbl = tkinter.Label(self.frame1, textvariable=textvariable, width=frame_width, anchor=tkinter.W,
                                     **kwargs)
            else:
                return

            _lbl.pack(fill=tkinter.BOTH, anchor=tkinter.W, pady=pady)

        def _button(text, command, pady=10, **kwargs):
            _btn = tkinter.Button(self.frame1, width=frame_width, text=text, command=command, **kwargs)
            _btn['relief'] = tkinter.RAISED
            _btn.pack(fill=tkinter.BOTH, anchor=tkinter.W, pady=pady)

        # info/control
        _label(text="status-------------------------")

        self.msg_status.set('ready')
        _label(textvariable=self.msg_status)

        self.msg_camera.set('no camera')
        _label(textvariable=self.msg_camera)

        self.msg_save.set('no camera')
        _label(textvariable=self.msg_save)

        _label(text="--------------------------------")
        _label(text="set capture_num")
        self.spin_capture = tkinter.Spinbox(self.frame1, from_=0, to=10000, increment=1,
                                            width=frame_width, textvariable=self.var_save)
        self.spin_capture.pack(fill=tkinter.BOTH, anchor=tkinter.W, pady=10)

        _label(text="--------------------------------")
        _button(text='Open Camera', command=self.open_camera)
        _button(text='Close Camera', command=self.close_camera)

        _button(text='Start Capture', command=self.start_capture)
        _button(text='Start Save', command=self.start_save)
        _button(text='Stop Capture', command=self.stop_capture)

    def set_frame2(self):

        cell = tkinter.Frame(self.frame2, width=self.cvs_w, height=self.cvs_h)
        cell.grid(row=1, column=1, padx=4, pady=4)
        cell.grid_propagate(False)

        self.cvs = Canvas(cell, width=self.cvs_w, height=self.cvs_h, highlightthickness=0)
        self.cvs.grid()

    def set_menu(self):
        menubar = tkinter.Menu(self.root)

        file_menu = tkinter.Menu(menubar)
        file_menu.add_command(label='exit', command=self.exit)
        menubar.add_cascade(label='File', menu=file_menu)

        self.root.config(menu=menubar)

    # Image Pipeline -----------------------------------
    def open_camera(self):
        if self.camera.is_opened:
            self.msg_status.set("camera is opened already")
            return

        self.camera = UsbCamera(camera_no=self.camera_no)

        try:
            self.camera.open()
            self.camera.set_params(width=self.cap_w, height=self.cap_h, fps=self.cap_fps)
        except Exception as err:
            self.msg_status.set(f"ERROR: open-camera failed: {err}")

        if self.camera.is_opened:
            self.msg_camera.set(f"camera{self.camera_no} ready")
            self.msg_save.set("ready")
            self.camera.show_params()
        else:
            self.msg_status.set("ERROR: open-camera failed")

    def close_camera(self):
        self.camera.close()

        self.msg_camera.set("no camera")
        self.msg_save.set("no camera")

    def start_capture(self):
        if self.capture_thread and self.capture_thread.is_alive():
            return

        self.stop_event.clear()
        self.save_event.clear()

        save_num = int(self.var_save.get())
        self.capture_thread = CaptureThread(camera=self.camera,
                                            frame_queue=self.frame_queue,
                                            stop_event=self.stop_event,
                                            save_event=self.save_event,
                                            target_fps=self.cap_fps if self.cap_fps is not None else 33,
                                            save_num=save_num,
                                            output_dir=self.out_dir)

        self.capture_thread.start()

        # 表示ループ開始
        self.update_frame()

    def stop_capture(self):
        if self.capture_thread is None or not self.capture_thread.is_alive():
            return

        self.save_event.clear()
        self.stop_event.set()

        try:
            self.capture_thread.join(timeout=1.0)
        except Exception:
            pass

        self.capture_thread = None
        self.msg_status.set("stop capture")
        self.msg_save.set("")

    def start_save(self):
        if self.capture_thread is None or not self.capture_thread.is_alive():
            return

        save_num = int(self.var_save.get())
        with self.capture_thread.lock:
            self.capture_thread.save_num = save_num

        if not self.save_event.is_set():
            self.capture_thread.start_save()
            self.msg_save.set("save on")

    def update_frame(self):
        if self.capture_thread is None or not self.capture_thread.is_alive():
            return

        self.msg_status.set(f"capture: {self.capture_thread.save_cnt}")
        if self.save_event.is_set():
            self.msg_save.set("save on")
        else:
            self.msg_save.set("ready")

        frame = self.frame_queue.get_latest()
        if frame is not None:
            data = ImageData(frame, self.cvs_h, self.cvs_w)
            self.cvs.set_image_data(image_data=data)

        self.root.after(30, lambda: self.update_frame())

    # misc-----------------------------------------------------------------------------------
    def resize_window(self, event):
        if self.capture_thread is not None and self.capture_thread.is_alive():
            return

        if event.widget is not self.root:
            return
        new_size = (event.width, event.height)
        if new_size == self._last_size:
            return
        if self.frame2 is None:
            return

        self._last_size = new_size

        # re-layout frame2
        for child in self.frame2.winfo_children():
            child.destroy()

        self.root_w = event.width
        self.root_h = event.height
        self.root.update_idletasks()

        f2_h = self.frame2.winfo_height()
        f2_w = self.frame2.winfo_width()
        self.cvs_h = int(f2_h * 0.95)
        self.cvs_w = int(f2_w * 0.95)
        self.set_frame2()


if __name__ == '__main__':
    CameraViewer(camera_no=0, cap_fps=20)
