import os, sys, glob, shutil, subprocess, tempfile, time
import numpy as np
import torch
from scipy import ndimage
from PIL import Image
import importlib.util

spec = importlib.util.spec_from_file_location('pp', r'C:/Users/admin/Desktop/MyPet/工具/预处理.py')
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)

# 朋友的酒（pyj）：邦多利全员Q弹（屏摄内窗），源 BV1fxHg6DEQ5「全体成员变得Q弹。」
# 音频另取 BV1hXbN6VEKV（活跃黑江乐）朋友的酒DJ → music/朋友的酒.m4a
SRC_V = os.path.join(pp.SRC, 'mat_pj_qt1.mp4')
OUTD = os.path.join(pp.OUT, 'pyj')
SS, DUR, FPS = 8.0, 20.0, 15
RECT = (0.097, 0.344, 0.943, 0.613)  # 屏摄内窗 (l,t,r,b)，三帧验证稳定

tmp = tempfile.mkdtemp(prefix='pj_')
cmd = ['ffmpeg', '-v', 'error', '-i', SRC_V, '-ss', str(SS), '-t', str(DUR),
       '-vf', 'crop=iw*{0}:ih*{1}:iw*{2}:ih*{3}'.format(RECT[2]-RECT[0], RECT[3]-RECT[1], RECT[0], RECT[1]),
       '-r', str(FPS), '-f', 'image2', os.path.join(tmp, '%05d.png')]
subprocess.run(cmd, capture_output=True, check=True)
files = sorted(glob.glob(os.path.join(tmp, '*.png')))
N = len(files)
print('抽取帧数:', N, flush=True)

model = torch.hub.load('PeterL1n/RobustVideoMatting', 'mobilenetv3', trust_repo=True).cuda().eval()
rec = [None] * 4
t0 = time.time()
keyed = []
for i, f in enumerate(files):
    im = Image.open(f).convert('RGB')
    arr = np.array(im)
    x = torch.from_numpy(arr).float().permute(2, 0, 1)[None] / 255.0
    with torch.no_grad():
        fgr, pha, *rec = model(x.cuda(), *rec, downsample_ratio=0.45)
    rm = ndimage.binary_fill_holes(pha[0, 0].cpu().numpy() > 0.5)
    # 色键抠像：从全画布出发，只删平色背景（蓝天/草地/天际线上方白云）；rm 做 2px 保护缓冲
    r_, g_, b_ = arr[..., 0].astype(int), arr[..., 1].astype(int), arr[..., 2].astype(int)
    mx = np.maximum(np.maximum(r_, g_), b_); mn = np.minimum(np.minimum(r_, g_), b_)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    lum = (r_ + g_ + b_) / 3.0
    yyidx = np.arange(arr.shape[0])[:, None]
    xxidx = np.arange(arr.shape[1])[None, :]
    sky = (b_ > r_ + 25) & (b_ > g_ + 10) & (lum > 85)               # 本片天空为青色(lum~109)；深蓝制服 lum~60 在 rm 保护内
    grass = (g_ > r_ + 18) & (g_ > b_ + 18) & (lum > 85)             # 近草
    hill = (g_ > r_ + 15) & (b_ > g_) & (lum > 80) & (yyidx > 0.45 * arr.shape[0]) & (yyidx < 0.585 * arr.shape[0])  # 远景草坡（青色）
    # 地平线以上的浅色区（白云+泛白雾霾）一并清除；头部白脸在 rm 内受保护
    haze = (lum > 150) & (sat < 0.22) & (yyidx < 0.62 * arr.shape[0])
    darkcloud = (sat < 0.20) & (yyidx < 0.30 * arr.shape[0]) & (xxidx > 0.58 * arr.shape[1]) & (lum < 170) & (lum > 30)  # 右上乌云
    key = sky | grass | hill | haze | darkcloud
    protect = ndimage.binary_dilation(rm, iterations=2)
    alpha = np.ones(arr.shape[:2], np.float32)
    alpha[key & ~protect] = 0.0
    lab, n = ndimage.label(alpha > 0.5)
    if n > 1:
        sizes = ndimage.sum_labels(np.ones_like(lab), lab, range(1, n + 1))
        big = sizes.max()
        keep = np.zeros(n + 1, bool); keep[1:] = sizes >= big * 0.015
        alpha = keep[lab].astype(np.float32)
    alpha = ndimage.binary_fill_holes(alpha > 0.5).astype(np.float32)
    am = ndimage.gaussian_filter(alpha, 0.8)
    a = (np.clip(am, 0, 1) * 255).astype(np.uint8)[..., None]
    a[:3] = 0; a[-3:] = 0; a[:, :3] = 0; a[:, -3:] = 0  # 屏摄内窗边缘线
    m = a[..., 0] < 8
    arr2 = arr.copy(); arr2[m] = 0; a[m] = 0
    keyed.append(Image.fromarray(np.concatenate([arr2, a], axis=2), 'RGBA'))
print('推理+色键: %.1f ms/帧' % ((time.time()-t0)*1000/N), flush=True)
shutil.rmtree(tmp, ignore_errors=True)

x0 = y0 = 10**9; x1 = y1 = -1
for k in keyed:
    bb = k.getbbox()
    if bb:
        x0 = min(x0, bb[0]); y0 = min(y0, bb[1]); x1 = max(x1, bb[2]); y1 = max(y1, bb[3])
uw, uh = x1-x0, y1-y0
s = min(620/uh, pp.CANVAS_W*0.9/uw, 1.15)
sw, sh = round(uw*s), round(uh*s)
print('union', (uw, uh), 'offset', (x0, y0), 'scale', round(s, 3), '->', (sw, sh))
os.makedirs(OUTD, exist_ok=True)
for old in glob.glob(os.path.join(OUTD, '*.png')):
    os.remove(old)
for i, k in enumerate(keyed):
    crop = k.crop((x0, y0, x1, y1)).resize((sw, sh), Image.LANCZOS)
    canvas = Image.new('RGBA', (pp.CANVAS_W, pp.CANVAS_H), (0, 0, 0, 0))
    canvas.paste(crop, ((pp.CANVAS_W-sw)//2, pp.CANVAS_H-sh), crop)
    canvas.save(os.path.join(OUTD, f'{i:04d}.png'))
print('完成', len(keyed), '帧 ->', OUTD, flush=True)

picks = [0, N//4, N//2, 3*N//4, N-1]
sheet = Image.new('RGB', (320*len(picks), 480), (30, 30, 34))
for j, idx in enumerate(picks):
    im = Image.open(os.path.join(OUTD, f'{idx:04d}.png')).convert('RGBA').resize((320, 480))
    bg = Image.new('RGBA', (320, 480)); px = bg.load()
    for y in range(0, 480, 16):
        for x in range(0, 320, 16):
            c = (70, 70, 76, 255) if (x//16+y//16) % 2 else (52, 52, 58, 255)
            for dy in range(16):
                for dx in range(16):
                    if x+dx < 320 and y+dy < 480: px[x+dx, y+dy] = c
    bg.alpha_composite(im)
    sheet.paste(bg.convert('RGB'), (j*320, 0))
sheet.save(r'C:/Users/admin/AppData/Local/Temp/pj_audit.jpg', quality=88)
print('审计图已存', flush=True)
