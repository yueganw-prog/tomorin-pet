import os, sys, glob, shutil, subprocess, tempfile, time
import numpy as np
import torch
from scipy import ndimage
from PIL import Image
import importlib.util

spec = importlib.util.spec_from_file_location('pp', r'C:/Users/admin/Desktop/MyPet/工具/预处理.py')
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)

SRC_V = os.path.join(pp.SRC, 'mat_qn_BV1ih.mp4')
OUTD = os.path.join(pp.OUT, 'qn_rvm')
SS, DUR, FPS = 62.0, 20.0, 12
CROP = (0.18, 0.26, 0.80, 1.0)  # l,t,r,b

tmp = tempfile.mkdtemp(prefix='rvm_')
cmd = ['ffmpeg', '-v', 'error', '-i', SRC_V, '-ss', str(SS), '-t', str(DUR),
       '-vf', 'crop=iw*{0}:ih*{1}:iw*{2}:ih*{3}'.format(CROP[2]-CROP[0], CROP[3]-CROP[1], CROP[0], CROP[1]),
       '-r', str(FPS), '-f', 'image2', os.path.join(tmp, '%05d.png')]
subprocess.run(cmd, capture_output=True, check=True)
files = sorted(glob.glob(os.path.join(tmp, '*.png')))
N = len(files)
print('抽取帧数:', N, flush=True)

model = torch.hub.load('PeterL1n/RobustVideoMatting', 'mobilenetv3', trust_repo=True).cuda().eval()
rec = [None] * 4
t0 = time.time()
keyed = []
rims = []
for i, f in enumerate(files):
    im = Image.open(f).convert('RGB')
    arr = np.array(im)
    H, W = arr.shape[:2]
    xx, yy = np.meshgrid(np.arange(W), np.arange(H))
    # --- RVM：时序稳定的身体 ---
    x = torch.from_numpy(arr).float().permute(2, 0, 1)[None] / 255.0
    with torch.no_grad():
        fgr, pha, *rec = model(x.cuda(), *rec, downsample_ratio=0.45)
    rm = ndimage.binary_fill_holes(pha[0, 0].cpu().numpy() > 0.85)
    rims.append(rm)
    # --- u2net：吉他细节；几何禁区排除右上的半透明鳍膜与墙面残留（琴颈不经过该区） ---
    u = np.array(pp.clean_alpha(pp.remove(im, session=pp.SESSION)).convert('RGBA'))[:, :, 3]
    ub = (u > 165) & ~((xx > 0.44 * W) & (yy < 0.42 * H))
    gate = ndimage.binary_dilation(rm, iterations=18)
    lab, n = ndimage.label(ub)
    if n > 1:
        keep = np.zeros(n + 1, bool)
        inter = ndimage.sum_labels(gate.astype(np.float32), lab, range(1, n + 1))
        keep[1:] = inter > 0
        ub = keep[lab]
    alpha = np.maximum(rm.astype(np.float32), ub.astype(np.float32))
    alpha = ndimage.binary_fill_holes(alpha > 0.5).astype(np.float32)
    am = ndimage.gaussian_filter(alpha, 0.8)
    a = (np.clip(am, 0, 1) * 255).astype(np.uint8)[..., None]
    m = a[..., 0] < 8
    arr2 = arr.copy(); arr2[m] = 0; a[m] = 0
    keyed.append(Image.fromarray(np.concatenate([arr2, a], axis=2), 'RGBA'))
print('混合推理: %.1f ms/帧' % ((time.time()-t0)*1000/N), flush=True)
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
# 窗户封闭区清除：画布坐标 (160-255, 475-610) → 素材帧坐标（含 union 偏移）。
# 该区（窗框/枯枝/鳍膜）在 rm 之外，矩形内一律清零；身体/琴颈（rm 内）受 3px 缓冲保护。
kx0 = int((160-32)/s)+x0; kx1 = int((255-32)/s)+x0
ky0 = int((475-387)/s)+y0; ky1 = int((610-387)/s)+y0
kill = np.zeros((H, W), bool)
kill[ky0:ky1, kx0:kx1] = True
print('kill rect(matted):', (kx0, ky0, kx1, ky1), flush=True)
os.makedirs(OUTD, exist_ok=True)
for old in glob.glob(os.path.join(OUTD, '*.png')):
    os.remove(old)
for i, k in enumerate(keyed):
    kArr = np.array(k)
    kArr[..., 3][kill & ~ndimage.binary_dilation(rims[i], iterations=3)] = 0
    k2 = Image.fromarray(kArr, 'RGBA')
    crop = k2.crop((x0, y0, x1, y1)).resize((sw, sh), Image.LANCZOS)
    canvas = Image.new('RGBA', (pp.CANVAS_W, pp.CANVAS_H), (0, 0, 0, 0))
    canvas.paste(crop, ((pp.CANVAS_W-sw)//2, pp.CANVAS_H-sh), crop)
    canvas.save(os.path.join(OUTD, f'{i:04d}.png'))
print('完成', len(keyed), '帧 ->', OUTD, flush=True)

picks = [0, 60, 120, 180, len(keyed)-1]
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
sheet.save(r'C:/Users/admin/AppData/Local/Temp/qn_audit_rvm.jpg', quality=88)
print('审计图已存', flush=True)
