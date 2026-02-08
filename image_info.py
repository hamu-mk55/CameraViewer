from typing import List, Optional, Tuple
from PIL import Image, ImageTk

import cv2
import numpy as np


class ImageData:
    def __init__(self, img_org, win_h, win_w, scale=1.0, img_path=None):
        self.img_org: np.ndarray = img_org
        self.win_h: int = win_h
        self.win_w: int = win_w

        self.scale: float = scale
        self.img_path = img_path

        self.fit_ratio: Optional[float] = None

        self.img_w_org = None
        self.img_h_org = None
        self.img_w_fit = None
        self.img_h_fit = None

        self._img_fit: Optional[np.ndarray] = None
        self._img_pil: Optional[Image] = None

        if img_org is not None:
            self.img_h_org, self.img_w_org = img_org.shape[:2]

        self._fit_window()

    def _fit_window(self):
        if self.img_org is None:
            return

        h_ratio = self.win_h / self.img_h_org
        w_ratio = self.win_w / self.img_w_org
        ratio = min(h_ratio, w_ratio) * self.scale

        self.fit_ratio = ratio
        self.img_h_fit = int(self.img_h_org * ratio)
        self.img_w_fit = int(self.img_w_org * ratio)
        self._img_fit = cv2.resize(self.img_org, (self.img_w_fit, self.img_h_fit))
        self._img_pil = self.cv2pil(self._img_fit)

    def img_fit(self, scale=None):
        if self.img_org is None:
            return None

        if scale is None:
            return self._img_fit

        if self.scale * 0.99 < scale < self.scale * 1.01:
            return self._img_fit

        self.scale = scale
        self._fit_window()
        return self._img_fit

    def img_pil(self, scale=None):
        if self.img_org is None:
            return None

        if scale is None:
            return self._img_pil

        if self.scale * 0.99 < scale < self.scale * 1.01:
            return self._img_pil

        self.scale = scale
        self._fit_window()
        return self._img_pil

    def cv2pil(self, img_cv: np.ndarray):
        """Convert OpenCV BGR/GRAY numpy image to PIL."""
        if img_cv is None:
            return None

        img = img_cv
        if img.ndim == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return Image.fromarray(img)


if __name__ == '__main__':
    pass
