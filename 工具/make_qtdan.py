import os, sys, glob, shutil, subprocess, tempfile, time, json, zipfile
import numpy as np
import torch
from scipy import ndimage
from PIL import Image
import importlib.util

spec = importlib.util.spec_from_file_location('pp', r'C:/Users/admin/Desktop/MyPet/工具/预处理.py')
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)

# 全员Q弹桌宠：独立素材包（id=qtan），复用色键抠像管线
SRC_V = os.path.join(pp.SRC, 'mat_pj_qt1.mp4')
PET_DIR = os.path.join(pp.ROOT, 'Q弹桌宠')
ASSET = os.path.join(PET_DIR, '资产')
SS_LAUGH, DUR_LAUGH = 8.0, 20.0   # 弹跳演出（与 资产/pyj 同段，直接复用）
SS_SING, DUR_SING = 30.0, 20.0    # 唱歌段（另一窗口，增加变化）
FPS = 15
RECT = (0.097, 0.344, 0.943, 0.613)  # 屏摄内窗

def extract(ss, dur, out):
    tmp = tempfile.mkdtemp(prefix='qtd_')
    cmd = ['ffmpeg', '-v', 'error', '-i', SRC_V, '-ss', str(ss), '-t', str(dur),
           '-vf', 'crop=iw*{0}:ih*{1}:iw*{2}:ih*{3}'.format(RECT[2]-RECT[0], RECT[3]-RECT[1], RECT[0], RECT[1]),
           '-r', str(FPS), '-f', 'image2', os.path.join(tmp, '%05d.png')]
    subprocess.run(cmd, capture_output=True, check=True)
    files = sorted(glob.glob(os.path.join(tmp, '*.png')))
    model = torch.hub.load('PeterL1n/RobustVideoMatting', 'mobilenetv3', trust_repo=True).cuda().eval()
    rec = [None] * 4
    keyed = []
    t0 = time.time()
    for i, f in enumerate(files):
        im = Image.open(f).convert('RGB')
        arr = np.array(im)
        x = torch.from_numpy(arr).float().permute(2, 0, 1)[None] / 255.0
        with torch.no_grad():
            fgr, pha, *rec = model(x.cuda(), *rec, downsample_ratio=0.45)
        rm = ndimage.binary_fill_holes(pha[0, 0].cpu().numpy() > 0.5)
        r_, g_, b_ = arr[..., 0].astype(int), arr[..., 1].astype(int), arr[..., 2].astype(int)
        mx = np.maximum(np.maximum(r_, g_), b_); mn = np.minimum(np.minimum(r_, g_), b_)
        sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
        lum = (r_ + g_ + b_) / 3.0
        yyidx = np.arange(arr.shape[0])[:, None]
        xxidx = np.arange(arr.shape[1])[None, :]
        sky = (b_ > r_ + 25) & (b_ > g_ + 10) & (lum > 85)
        grass = (g_ > r_ + 18) & (g_ > b_ + 18) & (lum > 85)
        hill = (g_ > r_ + 15) & (b_ > g_) & (lum > 80) & (yyidx > 0.45 * arr.shape[0]) & (yyidx < 0.585 * arr.shape[0])
        haze = (lum > 150) & (sat < 0.22) & (yyidx < 0.62 * arr.shape[0])
        darkcloud = (sat < 0.20) & (yyidx < 0.30 * arr.shape[0]) & (xxidx > 0.58 * arr.shape[1]) & (lum < 170) & (lum > 30)
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
        a[:3] = 0; a[-3:] = 0; a[:, :3] = 0; a[:, -3:] = 0
        m = a[..., 0] < 8
        arr2 = arr.copy(); arr2[m] = 0; a[m] = 0
        keyed.append(Image.fromarray(np.concatenate([arr2, a], axis=2), 'RGBA'))
        if i % 60 == 0: print('  %d/%d' % (i, len(files)), flush=True)
    shutil.rmtree(tmp, ignore_errors=True)
    # union → 画布
    x0 = y0 = 10**9; x1 = y1 = -1
    for k in keyed:
        bb = k.getbbox()
        if bb:
            x0 = min(x0, bb[0]); y0 = min(y0, bb[1]); x1 = max(x1, bb[2]); y1 = max(y1, bb[3])
    uw, uh = x1-x0, y1-y0
    s = min(620/uh, pp.CANVAS_W*0.9/uw, 1.15)
    sw, sh = round(uw*s), round(uh*s)
    print('  union', (uw, uh), 'scale', round(s, 3), '->', (sw, sh), flush=True)
    os.makedirs(out, exist_ok=True)
    for old in glob.glob(os.path.join(out, '*.png')):
        os.remove(old)
    for i, k in enumerate(keyed):
        crop = k.crop((x0, y0, x1, y1)).resize((sw, sh), Image.LANCZOS)
        canvas = Image.new('RGBA', (pp.CANVAS_W, pp.CANVAS_H), (0, 0, 0, 0))
        canvas.paste(crop, ((pp.CANVAS_W-sw)//2, pp.CANVAS_H-sh), crop)
        canvas.save(os.path.join(out, f'{i:04d}.png'))
    return len(keyed)

t0 = time.time()
print('== sing 段抠像 (t=%g-%gs) ==' % (SS_SING, SS_SING+DUR_SING), flush=True)
sing_n = extract(SS_SING, DUR_SING, os.path.join(ASSET, 'sing'))
print('== laugh 段：复用 资产/pyj (%d 帧) ==' % len(glob.glob(os.path.join(pp.OUT, 'pyj', '*.png'))), flush=True)
laugh_n = len(glob.glob(os.path.join(pp.OUT, 'pyj', '*.png')))
os.makedirs(os.path.join(ASSET, 'laugh'), exist_ok=True)
for f in glob.glob(os.path.join(pp.OUT, 'pyj', '*.png')):
    shutil.copyfile(f, os.path.join(ASSET, 'laugh', os.path.basename(f)))

# idle + look + blink 占位（Q弹素材无眼神/眨眼差分，静态复用）
idle = Image.open(os.path.join(ASSET, 'laugh', '0000.png'))
idle.save(os.path.join(ASSET, 'idle.png'))
os.makedirs(os.path.join(ASSET, 'look'), exist_ok=True)
for i in range(2):
    idle.save(os.path.join(ASSET, 'look', f'{i:02d}.png'))
for bank in (0, 1):
    os.makedirs(os.path.join(ASSET, 'blink', str(bank)), exist_ok=True)
    for i in range(2):
        idle.save(os.path.join(ASSET, 'blink', str(bank), f'{i:02d}.png'))

# 原声 wav（与 laugh 段对齐的 20s）
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', SRC_V, '-ss', str(SS_LAUGH), '-t', str(DUR_LAUGH),
                '-vn', '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', 2 if False else '2',
                os.path.join(PET_DIR, 'Q弹原声.wav')], check=True)

# 唱歌音频：活跃黑江乐 朋友的酒DJ
os.makedirs(os.path.join(PET_DIR, 'music'), exist_ok=True)
shutil.copyfile(os.path.join(pp.SRC, 'mat_pj_BV1hX.mp4'), os.path.join(tmp, 'song_src.mp4')) if False else None
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', os.path.join(pp.SRC, 'mat_pj_BV1hX.mp4'), '-vn', '-c:a', 'copy',
                os.path.join(PET_DIR, 'music', '朋友的酒.m4a')], check=True)

# 元数据 + 打包
meta = {
    "width": 640, "height": 960, "fps": 15.0, "frames": laugh_n,
    "eyeFrames": 2, "blinkFrames": 2, "blinkFps": 15,
    "name": "全员Q弹", "id": "qtan", "soundFile": "Q弹原声.wav",
    "poke": {"x": 445, "y": 760, "rx": 95, "ry": 85},
    "warp": {"top": 700, "bottom": 950, "rx": 260, "ry": 60},
    "icon": {"x": 350, "y": 640, "w": 200, "h": 200},
    "idleRect": {"x": 0.05, "y": 0.66, "w": 0.9, "h": 0.34},
    "sing": {"frames": sing_n, "fps": FPS},
    "songSeqs": {"朋友的酒.m4a": "sing"},
}
nwp = os.path.join(PET_DIR, '素材.nwp')
with zipfile.ZipFile(nwp, 'w', zipfile.ZIP_STORED) as z:
    z.write(os.path.join(ASSET, 'idle.png'), 'idle.png')
    for i in range(2):
        z.write(os.path.join(ASSET, 'look', f'{i:02d}.png'), f'look/{i:02d}.png')
    for bank in (0, 1):
        for i in range(2):
            z.write(os.path.join(ASSET, 'blink', str(bank), f'{i:02d}.png'), f'blink/{bank}/{i:02d}.png')
    for i in range(laugh_n):
        z.write(os.path.join(ASSET, 'laugh', f'{i:04d}.png'), f'laugh/{i:04d}.png')
    for i in range(sing_n):
        z.write(os.path.join(ASSET, 'sing', f'{i:04d}.png'), f'sing/{i:04d}.png')
    z.writestr('metadata.json', json.dumps(meta, ensure_ascii=False, indent=1))
print('素材.nwp 打包完成: laugh=%d sing=%d' % (laugh_n, sing_n), flush=True)

# 使用说明
with open(os.path.join(PET_DIR, '使用说明.txt'), 'w', encoding='utf-8') as f:
    f.write('''全员Q弹桌宠 · 使用说明

双击「Q弹桌宠.exe」启动（需与 素材.nwp 同目录）。
可与凑企鹅桌宠同时运行，互不干扰。

── 交互 ──
1. 待机：全员 Q弹 排排站，轻微弹跳
2. 双击：播放 Q弹弹跳演出 + 原声
3. 拖动/甩飞/戳碰/全屏隐藏：与凑企鹅一致

── 右键菜单 ──
唱歌：循环播放 music 文件夹里的歌（自带《朋友的酒》DJ 完整版）
通透原声 / 大小 / 总在最上面 / 全屏时自动隐藏 / 开机自启动 / 退出
（跳舞/飞踢/饿倒为本桌宠未提供的动作，点击无效果）

── 文件说明 ──
素材.nwp            全部形象帧（勿删）
Q弹原声.wav         双击时的原声
music/              歌曲文件夹（放入后重启生效）

── 数据位置 ──
%LOCALAPPDATA%\\NaiwaDesktopPet-qtan\\
''')
print('使用说明已写', flush=True)
print('全部完成，用时 %.0f s' % (time.time()-t0), flush=True)
