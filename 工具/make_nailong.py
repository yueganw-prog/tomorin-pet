import os, sys, glob, shutil, subprocess, tempfile, time, json, zipfile
import numpy as np
import torch
from scipy import ndimage
from PIL import Image
import importlib.util

spec = importlib.util.spec_from_file_location('pp', r'C:/Users/admin/Desktop/MyPet/工具/预处理.py')
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)

# 奶龙桌宠（nailong）：BV1NrxS6UERe 奶龙点单名场面，RVM 时序抠像
SRC_V = os.path.join(pp.SRC, 'mat_nailong.mp4')
PET_DIR = os.path.join(pp.ROOT, '奶龙桌宠')
ASSET = os.path.join(PET_DIR, '资产')
SS, DUR, FPS = 44.4, 4.4, 15
CROP = (0.30, 0.05, 0.65, 0.90)  # l,t,r,b —— 裁掉两侧与底部字幕

tmp = tempfile.mkdtemp(prefix='nl_')
cmd = ['ffmpeg', '-v', 'error', '-i', SRC_V, '-ss', str(SS), '-t', str(DUR),
       '-vf', 'crop=iw*{0}:ih*{1}:iw*{2}:ih*{3},scale=640:960'.format(CROP[2]-CROP[0], CROP[3]-CROP[1], CROP[0], CROP[1]),
       '-r', str(FPS), '-f', 'image2', os.path.join(tmp, '%05d.png')]
subprocess.run(cmd, capture_output=True, check=True)
files = sorted(glob.glob(os.path.join(tmp, '*.png')))
N = len(files)
print('抽取帧数:', N, flush=True)

model = torch.hub.load('PeterL1n/RobustVideoMatting', 'mobilenetv3', trust_repo=True).cuda().eval()
rec = [None] * 4
keyed = []
for i, f in enumerate(files):
    im = Image.open(f).convert('RGB')
    arr = np.array(im)
    x = torch.from_numpy(arr).float().permute(2, 0, 1)[None] / 255.0
    with torch.no_grad():
        fgr, pha, *rec = model(x.cuda(), *rec, downsample_ratio=0.45)
    p = pha[0, 0].cpu().numpy()
    # 前几帧的颈部阴影伪影：RVM 预热期用形态学开运算修边
    if i < 4:
        m = p > 0.5
        disk3 = np.zeros((7, 7), bool)
        dy, dx = np.mgrid[-3:4, -3:4]
        disk3[dy*dy + dx*dx <= 9] = True
        m = ndimage.binary_opening(m, structure=disk3)
        p = np.where(m, p, np.minimum(p, 0.3))
    alpha = np.clip(ndimage.gaussian_filter(p, 0.8), 0, 1)
    a = (alpha * 255).astype(np.uint8)[..., None]
    mk = a[..., 0] < 8
    arr2 = arr.copy(); arr2[mk] = 0; a[mk] = 0
    keyed.append(Image.fromarray(np.concatenate([arr2, a], axis=2), 'RGBA'))
    if i % 20 == 0: print('  %d/%d' % (i, N), flush=True)
shutil.rmtree(tmp, ignore_errors=True)

x0 = y0 = 10**9; x1 = y1 = -1
for k in keyed:
    bb = k.getbbox()
    if bb:
        x0 = min(x0, bb[0]); y0 = min(y0, bb[1]); x1 = max(x1, bb[2]); y1 = max(y1, bb[3])
uw, uh = x1-x0, y1-y0
s = min(620/uh, pp.CANVAS_W*0.9/uw, 1.15)
sw, sh = round(uw*s), round(uh*s)
print('union', (uw, uh), 'scale', round(s, 3), '->', (sw, sh))
os.makedirs(ASSET, exist_ok=True)
laugh_dir = os.path.join(ASSET, 'laugh')
os.makedirs(laugh_dir, exist_ok=True)
for old in glob.glob(os.path.join(laugh_dir, '*.png')):
    os.remove(old)
for i, k in enumerate(keyed):
    crop = k.crop((x0, y0, x1, y1)).resize((sw, sh), Image.LANCZOS)
    canvas = Image.new('RGBA', (pp.CANVAS_W, pp.CANVAS_H), (0, 0, 0, 0))
    canvas.paste(crop, ((pp.CANVAS_W-sw)//2, pp.CANVAS_H-sh), crop)
    canvas.save(os.path.join(laugh_dir, f'{i:04d}.png'))
laugh_n = len(keyed)
idle = Image.open(os.path.join(laugh_dir, '0000.png'))
idle.save(os.path.join(ASSET, 'idle.png'))
os.makedirs(os.path.join(ASSET, 'look'), exist_ok=True)
for i in range(2):
    idle.save(os.path.join(ASSET, 'look', f'{i:02d}.png'))
for bank in (0, 1):
    os.makedirs(os.path.join(ASSET, 'blink', str(bank)), exist_ok=True)
    for i in range(2):
        idle.save(os.path.join(ASSET, 'blink', str(bank), f'{i:02d}.png'))
sing_dir = os.path.join(ASSET, 'sing')
os.makedirs(sing_dir, exist_ok=True)
for old in glob.glob(os.path.join(sing_dir, '*.png')):
    os.remove(old)
for i in range(laugh_n):
    shutil.copyfile(os.path.join(laugh_dir, f'{i:04d}.png'), os.path.join(sing_dir, f'{i:04d}.png'))
sing_n = laugh_n

# 音频：奶龙点单名场面原声（对话+店内音，作为该桌宠的原声）
os.makedirs(os.path.join(PET_DIR, 'music'), exist_ok=True)
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', SRC_V, '-vn', '-c:a', 'copy',
                os.path.join(PET_DIR, 'music', '奶龙点单原声.m4a')], check=True)

meta = {
    "width": 640, "height": 960, "fps": 15.0, "frames": laugh_n,
    "eyeFrames": 2, "blinkFrames": 2, "blinkFps": 15,
    "name": "奶龙", "id": "nailong", "minimal": 1,
    "laughLabel": "点一杯（双击）",
    "idleRect": {"x": 0.2, "y": 0.1, "w": 0.6, "h": 0.8},
    "poke": {"x": 320, "y": 550, "rx": 110, "ry": 110},
    "warp": {"top": 400, "bottom": 940, "rx": 170, "ry": 70},
    "icon": {"x": 260, "y": 300, "w": 170, "h": 170},
    "sing": {"frames": sing_n, "fps": FPS},
    "idleSeq": "laugh",
    "songSeqs": {"奶龙点单原声.m4a": "sing"},
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
        z.write(os.path.join(laugh_dir, f'{i:04d}.png'), f'laugh/{i:04d}.png')
    for i in range(sing_n):
        z.write(os.path.join(sing_dir, f'{i:04d}.png'), f'sing/{i:04d}.png')
    z.writestr('metadata.json', json.dumps(meta, ensure_ascii=False, indent=1))
print('素材.nwp 打包完成: laugh=%d sing=%d' % (laugh_n, sing_n), flush=True)

with open(os.path.join(PET_DIR, '使用说明.txt'), 'w', encoding='utf-8') as f:
    f.write('''奶龙桌宠 · 使用说明

双击「奶龙桌宠.exe」启动（需与 素材.nwp 同目录）。
可与家族其他桌宠同时运行。

── 交互 ──
1. 待机：奶龙在奶茶店看着你（动态待机）
2. 双击：奶龙给你点一杯（原声）
3. 通用桌宠行为齐备

── 右键菜单 ──
点一杯（双击）/ ♪ 奶龙点单原声 / 退出奶龙
音频：切换背景音频

── 数据位置 ──
%LOCALAPPDATA%\\NaiwaDesktopPet-nailong\\
''')
print('全部完成', flush=True)
