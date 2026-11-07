import os, sys, glob, shutil, subprocess, tempfile, time, json, zipfile
import numpy as np
from scipy import ndimage
from PIL import Image
import importlib.util

spec = importlib.util.spec_from_file_location('pp', r'C:/Users/admin/Desktop/MyPet/工具/预处理.py')
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)

# 奶蛙家族套装：族谱视频里的白底 Q弹 chibi 逐只打包成独立桌宠
# 用法: python make_nai.py            → 打包 MEMBERS 里全部成员
#       python make_nai.py naishu ... → 只打包指定成员
SRC_V = os.path.join(pp.SRC, 'mat_fam_tree.mp4')
# (PetId, 名称, 片段前缀, 起始秒, 时长秒)
MEMBERS = [
    ('naishu', '奶鼠', 'shu', 33.0, 0.65, 228, 0.14, False),
    ('nainiu', '奶牛', 'niu', 34.55, 0.62, 228, 0.14, False),
    ('naihu',  '奶虎', 'hu',  36.35, 0.9, 228, 0.14),
    ('naitu',  '奶兔', 'tu',  40.9, 0.9, 228, 0.14, False, 0.90),
    ('nailong','奶龙', 'long', 1.6, 1.5, 140, 0.20, True),
]
ONLY = sys.argv[1:] if len(sys.argv) > 1 else None

def build_member(pid, name, prefix, ss, dur, w_lum=228, w_sat=0.14, aggressive=False, cut_bottom=None):
    pet_dir = os.path.join(pp.ROOT, name + '桌宠')
    asset = os.path.join(pet_dir, '资产')
    tmp = tempfile.mkdtemp(prefix='nai_')
    cmd = ['ffmpeg', '-v', 'error', '-i', SRC_V, '-ss', str(ss), '-t', str(dur),
           '-r', str(15), '-f', 'image2', os.path.join(tmp, '%05d.png')]
    subprocess.run(cmd, capture_output=True, check=True)
    files = sorted(glob.glob(os.path.join(tmp, '*.png')))
    # 滚动对齐：族谱模板内容持续上滚，逐帧按最大非白色块质心平移（弹跳保留，漂移抵消）
    centers = []
    for f0 in files:
        a0 = np.array(Image.open(f0).convert('RGB'))
        r0, g0, b0 = a0[...,0].astype(int), a0[...,1].astype(int), a0[...,2].astype(int)
        lum0 = (r0+g0+b0)/3.0
        mx0 = np.maximum(np.maximum(r0,g0),b0); mn0 = np.minimum(np.minimum(r0,g0),b0)
        sat0 = np.where(mx0>0, (mx0-mn0)/np.maximum(mx0,1), 0)
        green0 = (g0 > r0 + 30) & (g0 > b0 + 30) & (g0 > 110)
        nw = ~((lum0 > 225) & (sat0 < 0.15)) & ~green0
        lab0, n0 = ndimage.label(nw)
        if n0 > 0:
            sz0 = np.array(ndimage.sum_labels(np.ones_like(lab0), lab0, np.arange(1, n0+1)), dtype=np.float64)
            j0 = int(np.argmax(sz0))
            ys0, xs0 = np.where(lab0 == j0+1)
            centers.append((xs0.mean(), ys0.mean()))
        else:
            centers.append((a0.shape[1]/2, a0.shape[0]/2))
    ref = centers[len(centers)//2]
    keyed = []
    for i, f in enumerate(files):
        im0 = Image.open(f).convert('RGB')
        dx = max(-30, min(30, round(ref[0]-centers[i][0])))
        dy = max(-30, min(30, round(ref[1]-centers[i][1])))
        aligned = Image.new('RGB', im0.size, (255,255,255))
        aligned.paste(im0, (dx, dy))
        arr = np.array(aligned)
        H, W = arr.shape[:2]
        r_, g_, b_ = arr[..., 0].astype(int), arr[..., 1].astype(int), arr[..., 2].astype(int)
        lum = (r_ + g_ + b_) / 3.0
        mx = np.maximum(np.maximum(r_, g_), b_); mn = np.minimum(np.minimum(r_, g_), b_)
        sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
        white = (lum > w_lum) & (sat < w_sat)                       # 白底
        green = (g_ > r_ + 30) & (g_ > b_ + 30) & (g_ > 110)     # 绿色名牌
        blue_template = (b_ > g_ + 20) & (b_ > r_ + 20) & (lum < 150)  # 蓝色模板
        key = white | green | blue_template
        alpha = np.ones((H, W), np.float32)
        alpha[key] = 0.0
        if cut_bottom: alpha[int(cut_bottom * H):] = 0.0
        if aggressive:
            comp0 = alpha > 0.5
            comp0 = ndimage.binary_opening(comp0, structure=np.ones((9, 9), bool))
            comp0 = ndimage.binary_fill_holes(comp0)
            alpha = comp0.astype(np.float32)
        # 白色内窗边界清除：量取白区 bbox，向内收 4px，窗外全清
        wb = np.where((lum > 228) & (sat < 0.14))
        if len(wb[0]) > 1000:
            by0, by1 = int(np.percentile(wb[0], 1))+4, int(np.percentile(wb[0], 99))-4
            bx0, bx1 = int(np.percentile(wb[1], 1))+4, int(np.percentile(wb[1], 99))-4
            alpha[:by0, :] = 0; alpha[by1:, :] = 0
            alpha[:, :bx0] = 0; alpha[:, bx1:] = 0
        lab, n = ndimage.label(alpha > 0.5)
        if n > 0:
            sizes = np.array(ndimage.sum_labels(np.ones_like(lab), lab, np.arange(1, n+1)), dtype=np.float64)
            j = int(np.argmax(sizes))
            comp = lab == j+1
            comp = ndimage.binary_fill_holes(comp)
            alpha = comp.astype(np.float32)
        else:
            alpha = np.zeros((H, W), np.float32)
        am = ndimage.gaussian_filter(alpha, 0.8)
        a = (np.clip(am, 0, 1) * 255).astype(np.uint8)[..., None]
        mk = a[..., 0] < 8
        arr2 = arr.copy(); arr2[mk] = 0; a[mk] = 0
        keyed.append(Image.fromarray(np.concatenate([arr2, a], axis=2), 'RGBA'))
    shutil.rmtree(tmp, ignore_errors=True)
    x0 = y0 = 10**9; x1 = y1 = -1
    for k in keyed:
        bb = k.getbbox()
        if bb:
            x0 = min(x0, bb[0]); y0 = min(y0, bb[1]); x1 = max(x1, bb[2]); y1 = max(y1, bb[3])
    uw, uh = x1-x0, y1-y0
    s = min(560/uh, pp.CANVAS_W*0.82/uw, 3.0)  # chibi 小图允许 3 倍上采样
    sw, sh = round(uw*s), round(uh*s)
    print('  [%s] union %s scale %.2f -> %dx%d' % (name, (uw, uh), s, sw, sh), flush=True)
    os.makedirs(asset, exist_ok=True)
    laugh_n = 0
    laugh_dir = os.path.join(asset, 'laugh')
    os.makedirs(laugh_dir, exist_ok=True)
    for old in glob.glob(os.path.join(laugh_dir, '*.png')):
        os.remove(old)
    for i, k in enumerate(keyed):
        crop = k.crop((x0, y0, x1, y1)).resize((sw, sh), Image.LANCZOS)
        canvas = Image.new('RGBA', (pp.CANVAS_W, pp.CANVAS_H), (0, 0, 0, 0))
        canvas.paste(crop, ((pp.CANVAS_W-sw)//2, pp.CANVAS_H-sh), crop)
        canvas.save(os.path.join(laugh_dir, f'{i:04d}.png'))
        laugh_n += 1
    idle = Image.open(os.path.join(laugh_dir, '0000.png'))
    idle.save(os.path.join(asset, 'idle.png'))
    os.makedirs(os.path.join(asset, 'look'), exist_ok=True)
    for i in range(2):
        idle.save(os.path.join(asset, 'look', f'{i:02d}.png'))
    for bank in (0, 1):
        os.makedirs(os.path.join(asset, 'blink', str(bank)), exist_ok=True)
        for i in range(2):
            idle.save(os.path.join(asset, 'blink', str(bank), f'{i:02d}.png'))
    # ping-pong 到 sing 库（弹跳动作天然对称，倒放无缝）
    sing_dir = os.path.join(asset, 'sing')
    os.makedirs(sing_dir, exist_ok=True)
    for old in glob.glob(os.path.join(sing_dir, '*.png')):
        os.remove(old)
    idx = 0
    for i in range(laugh_n):
        shutil.copyfile(os.path.join(laugh_dir, f'{i:04d}.png'), os.path.join(sing_dir, f'{idx:04d}.png')); idx += 1
    for i in range(laugh_n-2, 0, -1):
        shutil.copyfile(os.path.join(laugh_dir, f'{i:04d}.png'), os.path.join(sing_dir, f'{idx:04d}.png')); idx += 1
    sing_n = idx
    meta = {
        "width": 640, "height": 960, "fps": 15.0, "frames": laugh_n,
        "eyeFrames": 2, "blinkFrames": 2, "blinkFps": 15,
        "name": name, "id": pid, "minimal": 1,
        "laughLabel": name + "跳一下（双击）",
        "idleRect": {"x": 0.15, "y": 0.25, "w": 0.7, "h": 0.7},
        "poke": {"x": 320, "y": 640, "rx": 120, "ry": 120},
        "warp": {"top": 500, "bottom": 930, "rx": 180, "ry": 70},
        "icon": {"x": 240, "y": 420, "w": 160, "h": 160},
        "sing": {"frames": sing_n, "fps": 15},
        "idleSeq": "laugh",
        "songSeqs": {},
    }
    nwp = os.path.join(pet_dir, '素材.nwp')
    with zipfile.ZipFile(nwp, 'w', zipfile.ZIP_STORED) as z:
        z.write(os.path.join(asset, 'idle.png'), 'idle.png')
        for i in range(2):
            z.write(os.path.join(asset, 'look', f'{i:02d}.png'), f'look/{i:02d}.png')
        for bank in (0, 1):
            for i in range(2):
                z.write(os.path.join(asset, 'blink', str(bank), f'{i:02d}.png'), f'blink/{bank}/{i:02d}.png')
        for i in range(laugh_n):
            z.write(os.path.join(laugh_dir, f'{i:04d}.png'), f'laugh/{i:04d}.png')
        for i in range(sing_n):
            z.write(os.path.join(sing_dir, f'{i:04d}.png'), f'sing/{i:04d}.png')
        z.writestr('metadata.json', json.dumps(meta, ensure_ascii=False, indent=1))
    os.makedirs(os.path.join(pet_dir, 'music'), exist_ok=True)
    print('  [%s] 完成: laugh=%d sing=%d(含倒放) -> %s' % (name, laugh_n, sing_n, pet_dir), flush=True)

t0 = time.time()
for mem in MEMBERS:
    vals = list(mem) + [228, 0.14, False]
    pid, name, prefix, ss, dur, w_lum, w_sat, aggressive, cut_bottom = (vals + [None])[:9]
    if ONLY and pid not in ONLY: continue
    print('== %s ==' % name, flush=True)
    build_member(pid, name, prefix, ss, dur)
print('全部完成，用时 %.0f s' % (time.time()-t0), flush=True)
