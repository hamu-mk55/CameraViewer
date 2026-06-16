import os
import tkinter
from typing import Optional
from tkinter import filedialog

import cv2
from PIL import ImageTk

from .image_info import ImageData


class Canvas(tkinter.Canvas):
    def __init__(self, root, **kwargs):
        super().__init__(root, **kwargs)

        self.cvs_id = None
        self.cvs_w = None
        self.cvs_h = None

        self.img_data: Optional[ImageData] = None
        self.img_pil = None
        self.img_id = None

        self.cwd = os.getcwd()
        self.right_click_menu = tkinter.Menu(self, tearoff=0)

        # Zoom
        self.scale = 1.0
        self.scale_ini = 1.0
        self.min_scale = 1.0
        self.max_scale = 5.0

        # Pan
        self.offset_x = 0
        self.offset_y = 0

        self.x0 = 0
        self.y0 = 0
        self.x1 = 0
        self.y1 = 0

        # EventBind
        self.bind("<Button-3>", self.right_click_function)
        self.bind("<MouseWheel>", self.on_mousewheel)
        self.bind("<ButtonPress-1>", self.on_mouse_press)
        self.bind("<B1-Motion>", self.on_mouse_drag)

    def set_image_data(self, image_data: ImageData, scale=1.0, reset_flg=False):
        if image_data is None:
            return

        first_flg = self.img_data is None or self.img_id is None

        self.img_data = image_data
        self.cvs_w = image_data.win_w
        self.cvs_h = image_data.win_h

        if self.img_data.img_org is not None:
            if first_flg or reset_flg:
                self.scale_ini = scale
                self.scale = scale
                self.img_data.img_fit(scale=scale)

                self.update_idletasks()
                center_cx = max(1, self.winfo_width()) / 2
                center_cy = max(1, self.winfo_height()) / 2
                center_ix = self.img_data.img_w_org / 2
                center_iy = self.img_data.img_h_org / 2

                self.offset_x = center_cx - center_ix * self.img_data.fit_ratio
                self.offset_y = center_cy - center_iy * self.img_data.fit_ratio
            else:
                self.img_data.img_fit(scale=scale)

        self._update_image()

    def _update_image(self, reset_flg=False):
        """scale と offset_x/y をもとに Canvas の画像を更新"""
        if self.img_data is None or self.img_data.img_org is None:
            return

        # Prepare TK-image
        self.img_pil = self.img_data.img_pil(scale=self.scale)
        self.tk_img = ImageTk.PhotoImage(self.img_pil)

        # Set Display
        if self.img_id is None or reset_flg:
            self.img_id = self.create_image(
                self.offset_x, self.offset_y, anchor="nw", image=self.tk_img
            )
        else:
            self.itemconfig(self.img_id, image=self.tk_img)
            self.coords(self.img_id, self.offset_x, self.offset_y)

    def check_offset(self):
        if self.img_data is None or self.img_data.img_org is None:
            return

        self.update_idletasks()
        cw = max(1, self.winfo_width())
        ch = max(1, self.winfo_height())

        iw, ih = self.img_data.img_pil().size

        if iw >= cw:
            min_x = cw - iw
            max_x = 0
            self.offset_x = max(min_x, min(max_x, self.offset_x))
        else:
            self.offset_x = (cw - iw) / 2

        if ih >= ch:
            min_y = ch - ih
            max_y = 0
            self.offset_y = max(min_y, min(max_y, self.offset_y))
        else:
            self.offset_y = (ch - ih) / 2

    # Right Click-----------------------------------------------------------
    def set_right_click_menu(self):
        self.right_click_menu.delete(0, "end")

        self.right_click_menu.add_command(label="save image", command=self.save_image)
        self.right_click_menu.add_command(label="reset view", command=self.reset_view)

    def right_click_function(self, event):
        self.set_right_click_menu()

        self.right_click_menu.tk_popup(event.x_root, event.y_root)
        self.right_click_menu.grab_release()

    # Mouse Events-----------------------------------------------------------

    def on_mousewheel(self, event):
        if self.img_data is None or self.img_data.img_org is None:
            return

        cx = self.canvasx(event.x)
        cy = self.canvasy(event.y)
        old_scale = self.scale

        # for Windows
        if hasattr(event, "delta") and event.delta != 0:
            zoom = 1.1 if event.delta > 0 else 0.9
        else:
            return

        new_scale = self.scale * zoom
        new_scale = max(self.min_scale, min(self.max_scale, new_scale))
        zoom = new_scale / old_scale
        if zoom == 1.0:
            return

        img_x = (cx - self.offset_x) / old_scale
        img_y = (cy - self.offset_y) / old_scale

        self.scale = new_scale

        self.offset_x = cx - img_x * self.scale
        self.offset_y = cy - img_y * self.scale

        self._update_image()
        self.check_offset()
        self._update_image()

    def on_mouse_press(self, event):
        self.x0 = event.x
        self.y0 = event.y

    def on_mouse_drag(self, event):
        dx = event.x - self.x0
        dy = event.y - self.y0

        self.offset_x += dx
        self.offset_y += dy

        self.x0 = event.x
        self.y0 = event.y

        self.check_offset()
        self._update_image()

    # Helper-----------------------------------------------------------------------------------------
    def save_image(self):
        if self.img_data is None or self.img_data.img_org is None:
            return

        img_path = filedialog.asksaveasfilename(initialdir=self.cwd)
        if not img_path:
            return
        cv2.imwrite(img_path, self.img_data.img_org)

    def reset_view(self):
        if self.img_data is None or self.img_data.img_org is None:
            return
        self.scale = self.scale_ini
        self.img_data.img_fit(scale=self.scale)

        try:
            self.xview_moveto(0)
            self.yview_moveto(0)
        except Exception:
            pass

        self.update_idletasks()
        center_cx = max(1, self.winfo_width()) / 2
        center_cy = max(1, self.winfo_height()) / 2

        center_ix = self.img_data.img_w_org / 2
        center_iy = self.img_data.img_h_org / 2

        self.offset_x = center_cx - center_ix * self.img_data.fit_ratio
        self.offset_y = center_cy - center_iy * self.img_data.fit_ratio

        self._update_image()
