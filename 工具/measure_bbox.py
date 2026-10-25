#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""采样视频帧，用 rembg 测量企鹅的 alpha 包围盒，确定裁剪框。"""
import subprocess, sys, io, os
import numpy as np
from PIL import Image
from rembg import remove, new_session

SESSION = new_session("isnet-general-use")

def frame_at(video, t):
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(t), "-i", video, "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True, check=True).stdout
    return Image.open(io.BytesIO(out)).convert("RGBA")

def bbox(im):
    arr = np.array(im)
    a = arr[:, :, 3]
    ys, xs = np.where(a > 24)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())

video = sys.argv[1]
times = [float(x) for x in sys.argv[2].split(",")]
W, H = None, None
for t in times:
    im = frame_at(video, t)
    if W is None:
        W, H = im.size
    cut = remove(im, session=SESSION)
    b = bbox(cut)
    print(f"t={t:>5}: size={im.size} bbox={b}")
