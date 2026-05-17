from typing import Optional

import cv2


class UsbCamera:
    def __init__(self, camera_no: int = 0):

        self._cam: Optional[cv2.VideoCapture] = None
        self._camera_no = camera_no

        self.is_opened = False

    def open(self):
        try:
            self._cam = cv2.VideoCapture(self._camera_no)
        except Exception as err:
            raise IOError(
                f"ERROR: Camera{self._camera_no} cannnot be opened\n" f"{err}"
            )

        if not self._cam.isOpened():
            self._cam.release()
            self._cam = None
            self.is_opened = False
            raise IOError(f"ERROR: Camera {self._camera_no} cannot be opened")

        self.is_opened = True

    def close(self):
        if self._cam is not None:
            self._cam.release()
            self._cam = None

        self.is_opened = False

    def set_params(self, width=None, height=None, fps=None, debug: bool = False):

        if self._cam is None:
            raise IOError("Camera is not set")
        if not self._cam.isOpened():
            raise IOError("Camera is not opened")
        if not self.is_opened:
            raise IOError("Camera is not opened")

        if height is not None:
            self._cam.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
        if width is not None:
            self._cam.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
        if fps is not None:
            self._cam.set(cv2.CAP_PROP_FPS, int(fps))

        if debug:
            self.show_params()

        return {
            "width": self._cam.get(cv2.CAP_PROP_FRAME_WIDTH),
            "height": self._cam.get(cv2.CAP_PROP_FRAME_HEIGHT),
            "fps": self._cam.get(cv2.CAP_PROP_FPS),
        }

    def capture(self):
        if self._cam is None:
            raise IOError("Camera is not set")
        if not self._cam.isOpened():
            raise IOError("Camera is not opened")
        if not self.is_opened:
            raise IOError("Camera is not opened")

        ret, frame = self._cam.read()

        if frame is None:
            self.is_opened = False
            return None

        return frame

    def show_params(self):
        print("BRIGHTNESS:", self._cam.get(cv2.CAP_PROP_BRIGHTNESS))
        print("GAIN:", self._cam.get(cv2.CAP_PROP_GAIN))
        print("SATURATION:", self._cam.get(cv2.CAP_PROP_SATURATION))
        print("SETTING:", self._cam.get(cv2.CAP_PROP_SETTINGS))
        print("WHITE BALANCE B:", self._cam.get(cv2.CAP_PROP_WHITE_BALANCE_BLUE_U))
        print("WHITE BALANCE R:", self._cam.get(cv2.CAP_PROP_WHITE_BALANCE_RED_V))
        print("WIDTH:", self._cam.get(cv2.CAP_PROP_FRAME_WIDTH))
        print("HEIGHT:", self._cam.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print("EXPOSURE:", self._cam.get(cv2.CAP_PROP_EXPOSURE))
        print("MSEC:", self._cam.get(cv2.CAP_PROP_POS_MSEC))
        print("MODE:", self._cam.get(cv2.CAP_PROP_MODE))
        print("FPS:", self._cam.get(cv2.CAP_PROP_FPS))
        print("GUID:", self._cam.get(cv2.CAP_PROP_GUID))
        print("FOURCC:", self._cam.get(cv2.CAP_PROP_FOURCC))


if __name__ == "__main__":
    camera = UsbCamera(camera_no=0)
    camera.set_params()
