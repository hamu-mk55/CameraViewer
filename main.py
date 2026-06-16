import os
import threading
from dataclasses import dataclass, replace
from typing import Optional

import tkinter
from tkinter import ttk, messagebox

from src.image_info import ImageData
from src.canvas import Canvas
from src.usb_camera import UsbCamera
from src.camera_capture import FrameQueue, CaptureThread


@dataclass
class CameraSettings:
    camera_no: int
    width: int
    height: int
    fps: int

    def copy(self):
        return replace(self)

    def to_params(self):
        return {
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
        }


class CameraViewer:
    def __init__(self, camera_no=0, cap_w=640, cap_h=480, cap_fps=20):
        self.root = tkinter.Tk()
        self.root.title("Camera Viewer")
        self.root.geometry("1000x700")
        self.root.minsize(860, 560)
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self.close_window)
        self._setup_style()

        # image params
        self.cvs: Optional[Canvas] = None

        # Camera
        self.settings = CameraSettings(
            camera_no=camera_no,
            width=cap_w,
            height=cap_h,
            fps=cap_fps,
        )
        self.camera = UsbCamera(camera_no=camera_no)

        self.stop_event = threading.Event()
        self.frame_queue = FrameQueue(maxsize=1)
        self.capture_thread = None

        # Save
        self.out_dir = "./images"
        self.save_event = threading.Event()
        self.save_started = False

        # Etc
        self.root.bind("<Configure>", self.resize_window)
        self._last_size = (0, 0)

        # Frames
        self.root.update_idletasks()
        self.frame1 = None
        self.frame2 = None
        self.cvs_h = None
        self.cvs_w = None

        # UI elements
        self.msg_status = tkinter.StringVar()
        self.msg_camera = tkinter.StringVar()
        self.msg_save = tkinter.StringVar()

        self.var_camera_no = tkinter.StringVar(value=str(camera_no))
        self.var_fps = tkinter.StringVar(
            value=str(cap_fps if cap_fps is not None else 33)
        )
        self.var_width = tkinter.StringVar(
            value=str(cap_w if cap_w is not None else "")
        )
        self.var_height = tkinter.StringVar(
            value=str(cap_h if cap_h is not None else "")
        )
        self.var_save = tkinter.StringVar(value="0")
        self.var_save_id = tkinter.StringVar(value="")

        self.spin_camera_no = None
        self.spin_fps = None
        self.spin_width = None
        self.spin_height = None
        self.spin_capture = None
        self.entry_save_id = None

        self.settings_window = None

        self.btn_open_camera = None
        self.btn_close_camera = None
        self.btn_start_capture = None
        self.btn_start_save = None
        self.btn_stop_capture = None

        self.btn_apply_settings = None

        self.settings_menu_index = None
        self.menubar = None

        # build UI
        self.set_frames()
        self.root.mainloop()

    def _setup_style(self):
        self.style = ttk.Style(self.root)
        self.style.configure(".", font=("Yu Gothic UI", 10))
        self.style.configure("Title.TLabel", font=("Yu Gothic UI", 14, "bold"))
        self.style.configure("Section.TLabel", font=("Yu Gothic UI", 10, "bold"))
        self.style.configure("TButton", padding=(8, 4))
        self.style.configure("TSpinbox", padding=(8, 6))

    def exit(self):
        try:
            self.stop_capture()
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
        if messagebox.askokcancel("Exit", "Close Camera Viewer?"):
            self.exit()

    # ---- UI build ---------------------------------------
    def set_frames(self):
        for child in self.root.winfo_children():
            child.destroy()

        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)

        # left: info/control
        self.frame1 = ttk.Frame(self.root, width=280, padding=(18, 18, 18, 18))
        self.frame1.grid(row=1, column=0, sticky="ns")
        self.frame1.grid_propagate(False)

        # right: images
        self.frame2 = ttk.Frame(self.root, padding=(16, 16, 16, 16))
        self.frame2.grid(row=1, column=1, sticky="nsew")
        self.frame2.grid_rowconfigure(0, weight=1)
        self.frame2.grid_columnconfigure(0, weight=1)

        self.set_frame1()

        self.root.update_idletasks()
        f2_h = self.frame2.winfo_height()
        f2_w = self.frame2.winfo_width()
        self.cvs_h = int(f2_h * 0.95)
        self.cvs_w = int(f2_w * 0.95)
        self.set_frame2()

        self.set_menu()

    def set_frame1(self, frame_width=20):
        def _label(text=None, textvariable=None, style="TLabel", pady=(0, 4), **kwargs):
            if text is not None:
                _lbl = ttk.Label(self.frame1, text=text, style=style, **kwargs)
            elif textvariable is not None:
                _lbl = ttk.Label(
                    self.frame1, textvariable=textvariable, style=style, **kwargs
                )
            else:
                return

            _lbl.pack(fill=tkinter.X, anchor=tkinter.W, pady=pady)

        def _button(text, command, pady=(0, 4), style="TButton", **kwargs):
            _btn = ttk.Button(
                self.frame1, text=text, command=command, style=style, **kwargs
            )
            _btn.pack(fill=tkinter.X, anchor=tkinter.W, pady=pady)
            return _btn

        _label(text="Status", style="Section.TLabel", pady=(0, 8))

        self.msg_status.set("")
        _label(textvariable=self.msg_status, pady=(0, 8))

        self.msg_camera.set(self._camera_status_text())
        _label(textvariable=self.msg_camera, pady=(0, 5))

        self.msg_save.set("")
        _label(textvariable=self.msg_save, pady=(0, 14))

        ttk.Separator(self.frame1).pack(fill=tkinter.X, pady=(0, 16))

        _label(text="Save Count", style="Section.TLabel", pady=(0, 8))
        _label(text="0 means unlimited", pady=(0, 6))
        self.spin_capture = ttk.Spinbox(
            self.frame1,
            from_=0,
            to=10000,
            increment=1,
            width=frame_width,
            textvariable=self.var_save,
            justify=tkinter.RIGHT,
        )
        self.spin_capture.pack(fill=tkinter.X, anchor=tkinter.W, pady=(0, 18))

        _label(text="Save ID", style="Section.TLabel", pady=(0, 8))
        self.entry_save_id = ttk.Entry(
            self.frame1,
            width=frame_width,
            textvariable=self.var_save_id,
        )
        self.entry_save_id.pack(fill=tkinter.X, anchor=tkinter.W, pady=(0, 18))

        ttk.Separator(self.frame1).pack(fill=tkinter.X, pady=(0, 16))

        _label(text="Camera", style="Section.TLabel", pady=(0, 8))
        self.btn_open_camera = _button(text="Open Camera", command=self.open_camera)
        self.btn_close_camera = _button(text="Close Camera", command=self.close_camera)

        ttk.Separator(self.frame1).pack(fill=tkinter.X, pady=(8, 16))

        _label(text="Capture", style="Section.TLabel", pady=(0, 8))
        self.btn_start_capture = _button(
            text="Start Preview", command=self.start_capture
        )
        self.btn_start_save = _button(text="Start Save", command=self.start_save)
        self.btn_stop_capture = _button(
            text="Stop", command=self.stop_capture, pady=(0, 0)
        )

    def set_frame2(self):
        cell = ttk.Frame(
            self.frame2,
            width=self.cvs_w,
            height=self.cvs_h,
            padding=1,
        )
        cell.grid(row=0, column=0, sticky="nsew")
        cell.grid_propagate(False)
        cell.grid_rowconfigure(0, weight=1)
        cell.grid_columnconfigure(0, weight=1)

        self.cvs = Canvas(
            cell,
            width=self.cvs_w,
            height=self.cvs_h,
            highlightthickness=0,
            bg="#0b1120",
        )
        self.cvs.grid(row=0, column=0, sticky="nsew")

    def set_menu(self):
        menubar = tkinter.Menu(self.root)

        file_menu = tkinter.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Exit", command=self.exit)
        menubar.add_cascade(label="File", menu=file_menu)
        menubar.add_command(label="Settings", command=self.open_settings_window)
        self.settings_menu_index = menubar.index("end")
        self.menubar = menubar

        self.root.config(menu=menubar)
        self.update_control_states()

    def _setting_spinbox(self, parent, label, textvariable, from_, to, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=5)
        spinbox = ttk.Spinbox(
            parent,
            from_=from_,
            to=to,
            increment=1,
            width=12,
            textvariable=textvariable,
            justify=tkinter.RIGHT,
        )
        spinbox.grid(row=row, column=1, sticky="ew", pady=5)
        return spinbox

    def _set_widget_enabled(self, widget, enabled):
        if widget is not None:
            widget.configure(state=tkinter.NORMAL if enabled else tkinter.DISABLED)

    def is_camera_connected(self):
        return self.camera.is_opened

    def is_previewing(self):
        return self.capture_thread is not None and self.capture_thread.is_alive()

    def is_saving(self):
        return self.save_event.is_set()

    def update_control_states(self):
        camera_connected = self.is_camera_connected()
        is_saving = self.is_saving()
        is_previewing = self.is_previewing()
        camera_no_enabled = not camera_connected
        capture_settings_enabled = not is_previewing and not is_saving
        apply_enabled = not is_previewing and not is_saving

        self._set_widget_enabled(self.btn_open_camera, not camera_connected)
        self._set_widget_enabled(self.btn_close_camera, camera_connected)
        self._set_widget_enabled(self.btn_start_capture, camera_connected)
        self._set_widget_enabled(self.btn_start_save, camera_connected)
        self._set_widget_enabled(self.btn_stop_capture, camera_connected)

        self._set_widget_enabled(self.spin_camera_no, camera_no_enabled)
        self._set_widget_enabled(self.entry_save_id, not is_saving)

        for widget in (self.spin_fps, self.spin_width, self.spin_height):
            self._set_widget_enabled(widget, capture_settings_enabled)

        self._set_widget_enabled(self.btn_apply_settings, apply_enabled)

    def open_settings_window(self):
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.lift()
            self.settings_window.focus_set()
            self.update_control_states()
            return

        win = tkinter.Toplevel(self.root)
        self.settings_window = win
        win.title("Camera Settings")
        win.resizable(False, False)
        win.transient(self.root)
        win.protocol("WM_DELETE_WINDOW", self.close_settings_window)

        body = ttk.Frame(win, padding=(16, 14, 16, 12))
        body.grid(row=0, column=0, sticky="nsew")
        body.grid_columnconfigure(1, weight=1)

        self.spin_camera_no = self._setting_spinbox(
            body, "Camera No", self.var_camera_no, 0, 10, 0
        )
        self.spin_fps = self._setting_spinbox(body, "FPS", self.var_fps, 1, 240, 1)
        self.spin_width = self._setting_spinbox(
            body, "Width", self.var_width, 1, 7680, 2
        )
        self.spin_height = self._setting_spinbox(
            body, "Height", self.var_height, 1, 4320, 3
        )

        buttons = ttk.Frame(body)
        buttons.grid(row=4, column=0, columnspan=2, sticky="e", pady=(14, 0))
        self.btn_apply_settings = ttk.Button(
            buttons, text="Apply", command=self.apply_settings
        )
        self.btn_apply_settings.pack(side=tkinter.LEFT, padx=(0, 6))
        ttk.Button(buttons, text="Close", command=self.close_settings_window).pack(
            side=tkinter.LEFT
        )
        self.update_control_states()

    def close_settings_window(self):
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.destroy()
        self.settings_window = None
        self.spin_camera_no = None
        self.spin_fps = None
        self.spin_width = None
        self.spin_height = None
        self.btn_apply_settings = None

    def _sync_settings_vars(self):
        self.var_camera_no.set(str(self.settings.camera_no))
        self.var_fps.set(str(self.settings.fps))
        self.var_width.set(str(self.settings.width))
        self.var_height.set(str(self.settings.height))

    def _sync_actual_camera_params(self, actual_params, requested_settings):
        # fps is synced if possible, but if not available, use requested fps
        actual_w = int(round(actual_params.get("width") or requested_settings.width))
        actual_h = int(round(actual_params.get("height") or requested_settings.height))

        self.settings = CameraSettings(
            camera_no=requested_settings.camera_no,
            width=actual_w,
            height=actual_h,
            fps=requested_settings.fps,
        )
        self._sync_settings_vars()

        if (
            actual_w != requested_settings.width
            or actual_h != requested_settings.height
        ):
            return (
                "Settings adjusted by camera:\n"
                f"{requested_settings.width}x{requested_settings.height} -> "
                f"{actual_w}x{actual_h}"
            )

        return None

    def _apply_camera_settings(self, requested_settings):
        actual_params = self.camera.set_params(**requested_settings.to_params())
        return self._sync_actual_camera_params(actual_params, requested_settings)

    def _open_camera_with_settings(self, requested_settings):
        self.camera = UsbCamera(camera_no=requested_settings.camera_no)
        self.camera.open()
        return self._apply_camera_settings(requested_settings)

    def _reopen_camera_with_settings(self, requested_settings):
        self.camera.close()
        self.camera.open()
        return self._apply_camera_settings(requested_settings)

    def apply_settings(self):
        old_settings = self.settings.copy()

        requested_settings = self._read_capture_settings()
        if requested_settings is None:
            return

        is_capturing = self.is_previewing()

        if is_capturing or self.is_saving():
            self.settings = old_settings
            self._sync_settings_vars()
            self.msg_status.set("ERROR: stop preview/save before changing settings")
            self.update_control_states()
            return

        if (
            self.camera.is_opened
            and requested_settings.camera_no != old_settings.camera_no
        ):
            self.settings = old_settings
            self._sync_settings_vars()
            self.msg_status.set("ERROR: close camera before changing camera number")
            return

        changed_settings = requested_settings != old_settings
        changed_camera_settings = (
            requested_settings.width != old_settings.width
            or requested_settings.height != old_settings.height
            or requested_settings.fps != old_settings.fps
        )
        self.settings = requested_settings
        status_message = None

        if self.camera.is_opened:
            try:
                if changed_camera_settings:
                    status_message = self._reopen_camera_with_settings(
                        requested_settings
                    )
            except Exception as err:
                self.settings = old_settings
                self._sync_settings_vars()
                try:
                    self._reopen_camera_with_settings(old_settings)
                except Exception:
                    pass
                self.msg_status.set(f"ERROR: camera params failed: {err}")
                return

        self._set_camera_status(is_capturing=is_capturing)
        if status_message is not None:
            self.msg_status.set(status_message)
        elif changed_settings:
            self.msg_status.set("Settings applied")
        else:
            self.msg_status.set("Settings unchanged")

    # Image Pipeline -----------------------------------
    def _clear_tool_status(self):
        self.msg_status.set("")

    def _camera_status_text(self, is_capturing=False):
        status = "Capturing" if is_capturing else "Connected"

        if not self.camera.is_opened:
            return "No Camera Connected"

        return f"Camera{self.settings.camera_no} {status}: "

    def _set_camera_status(self, is_capturing=False):
        self.msg_camera.set(self._camera_status_text(is_capturing=is_capturing))
        self.update_control_states()

    def _save_target_text(self, save_num):
        return "unlimited" if save_num <= 0 else str(save_num)

    def _set_save_status(self, text=""):
        self.msg_save.set(text)

    def _read_capture_settings(self) -> Optional[CameraSettings]:
        try:
            camera_no = int(self.var_camera_no.get())
            if camera_no < 0:
                raise ValueError
        except ValueError:
            self.msg_status.set("ERROR: camera number must be 0 or more")
            return None

        try:
            cap_fps = int(self.var_fps.get())
            if cap_fps <= 0:
                raise ValueError
        except ValueError:
            self.msg_status.set("ERROR: FPS must be 1 or more")
            return None

        try:
            cap_w = int(self.var_width.get())
            if cap_w <= 0:
                raise ValueError
        except ValueError:
            self.msg_status.set("ERROR: width must be 1 or more")
            return None

        try:
            cap_h = int(self.var_height.get())
            if cap_h <= 0:
                raise ValueError
        except ValueError:
            self.msg_status.set("ERROR: height must be 1 or more")
            return None

        return CameraSettings(
            camera_no=camera_no,
            width=cap_w,
            height=cap_h,
            fps=cap_fps,
        )

    def _read_save_num(self):
        try:
            save_num = int(self.var_save.get())
            if save_num < 0:
                raise ValueError
        except ValueError:
            self.msg_status.set("ERROR: save count must be 0 or more")
            return None

        return save_num

    def _read_save_id(self):
        return self.var_save_id.get().strip()

    def open_camera(self):
        self._clear_tool_status()
        self.save_started = False
        self._set_save_status()

        if self.camera.is_opened:
            self._set_camera_status()
            return

        requested_settings = self._read_capture_settings()
        if requested_settings is None:
            return

        status_message = None

        try:
            status_message = self._open_camera_with_settings(requested_settings)
        except Exception as err:
            self.msg_status.set(f"ERROR: open-camera failed: {err}")

        if self.camera.is_opened:
            self._set_camera_status()
            self._set_save_status()
            if status_message is not None:
                self.msg_status.set(status_message)
            self.camera.show_params()
        else:
            self._set_camera_status()
            self.msg_status.set("ERROR: open-camera failed")

    def close_camera(self):
        self._clear_tool_status()
        self.save_started = False
        self._set_save_status()

        if self.is_previewing():
            self.save_event.clear()
            self.stop_event.set()
            try:
                self.capture_thread.join(timeout=1.0)
            except Exception:
                pass
            self.capture_thread = None

        self.camera.close()
        self._set_camera_status()

    def start_capture(self):
        self._clear_tool_status()
        self.save_started = False
        self._set_save_status()

        if self.is_previewing():
            self._set_camera_status(is_capturing=True)
            return

        if self.camera.is_opened:
            try:
                selected_camera_no = int(self.var_camera_no.get())
            except ValueError:
                self.msg_status.set("ERROR: camera number must be 0 or more")
                return
            if selected_camera_no != self.settings.camera_no:
                self._set_camera_status()
                self.msg_status.set("ERROR: close camera before changing camera number")
                return

        if not self.camera.is_opened:
            self._set_camera_status()
            self.msg_status.set("ERROR: camera is not connected")
            return

        self.frame_queue.clear()
        self.stop_event.clear()
        self.save_event.clear()

        save_num = self._read_save_num()
        if save_num is None:
            return

        self.capture_thread = CaptureThread(
            camera=self.camera,
            frame_queue=self.frame_queue,
            stop_event=self.stop_event,
            save_event=self.save_event,
            target_fps=self.settings.fps if self.settings.fps is not None else 33,
            save_num=save_num,
            output_dir=self.out_dir,
        )

        self.capture_thread.start()
        self._set_camera_status(is_capturing=True)

        self.update_frame()

    def stop_capture(self):
        self._clear_tool_status()
        self.save_started = False
        self._set_save_status()

        if not self.is_previewing():
            self._set_camera_status()
            return

        self.save_event.clear()
        self.stop_event.set()

        try:
            self.capture_thread.join(timeout=1.0)
        except Exception:
            pass

        self.capture_thread = None
        self._set_camera_status()

    def start_save(self):
        self._clear_tool_status()

        if not self.is_previewing():
            self.msg_status.set("ERROR: capture is not running")
            return

        save_num = self._read_save_num()
        if save_num is None:
            return
        save_id = self._read_save_id()

        with self.capture_thread.lock:
            self.capture_thread.save_num = save_num

        if not self.is_saving():
            self.capture_thread.start_save(save_id=save_id)
            self.save_started = True
            self._set_save_status(f" Save Images: 0/{self._save_target_text(save_num)}")

    def update_frame(self):
        if self.capture_thread is None:
            return

        if not self.capture_thread.is_alive():
            error_message = self.capture_thread.error_message
            self.capture_thread = None
            self.save_event.clear()
            self.stop_event.set()
            self.save_started = False
            self._set_camera_status()
            self._set_save_status()

            if error_message:
                self.msg_status.set(f"ERROR: {error_message}")
            return

        try:
            self._set_camera_status(is_capturing=True)
            save_cnt = self.capture_thread.save_cnt
            save_num = self.capture_thread.save_num
            if self.is_saving():
                self._set_save_status(
                    f" Save Images: {save_cnt}/{self._save_target_text(save_num)}"
                )
            elif (
                self.capture_thread.output_dir is not None
                and save_num > 0
                and save_cnt >= save_num
                and self.save_started
            ):
                self._set_save_status("Complete")
            else:
                self._set_save_status()

            frame = self.frame_queue.get_latest()
            if frame is not None:
                data = ImageData(frame, self.cvs_h, self.cvs_w)
                self.cvs.set_image_data(image_data=data)
        except Exception as err:
            self.msg_status.set(f"ERROR: preview update failed: {err}")
        finally:
            self.root.after(30, lambda: self.update_frame())

    # misc-----------------------------------------------------------------------------------
    def resize_window(self, event):
        if self.is_previewing():
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

        self.root.update_idletasks()

        f2_h = self.frame2.winfo_height()
        f2_w = self.frame2.winfo_width()
        self.cvs_h = int(f2_h * 0.95)
        self.cvs_w = int(f2_w * 0.95)
        self.set_frame2()


if __name__ == "__main__":
    CameraViewer(camera_no=0, cap_w=640, cap_h=480, cap_fps=20)
