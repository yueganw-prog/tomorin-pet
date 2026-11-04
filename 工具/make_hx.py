import os, sys, glob, shutil, subprocess, tempfile, time, json, zipfile
import numpy as np
from scipy import ndimage
from PIL import Image
import importlib.util

spec = importlib.util.spec_from_file_location('pp', r'C:/Users/admin/Desktop/MyPet/工具/预处理.py')
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)

# 小浣熊桌宠（hx）：BV1Bbpt6iE6X 浣熊跳舞（独舞），u2net 最大色块抠像
# 音频：BV1Racvz3Ero《落泪DJ》完整版（我真的特别爱你为什么你会流泪）
SRC_V = os.path.join(pp.SRC, 'mat_hx_dance.mp4')
PET_DIR = os.path.join(pp.ROOT, '浣熊桌宠')
ASSET = os.path.join(PET_DIR, '资产')
SS_LAUGH, DUR_LAUGH = 25.0, 20.0
SS_SING, DUR_SING = 70.0, 20.0
FPS = 15
CROP = (0.24, 0.05, 0.68, 0.97)  # l,t,r,b —— 避开左侧水印与底部字幕，保持人物比例

def extract(ss, dur, out):
    tmp = tempfile.mkdtemp(prefix='hx_')
    cmd = ['ffmpeg', '-v', 'error', '-i', SRC_V, '-ss', str(ss), '-t', str(dur),
           '-vf', 'crop=iw*{0}:ih*{1}:iw*{2}:ih*{3},scale=512:-2'.format(CROP[2]-CROP[0], CROP[3]-CROP[1], CROP[0], CROP[1]),
           '-r', str(FPS), '-f', 'image2', os.path.join(tmp, '%05d.png')]
    subprocess.run(cmd, capture_output=True, check=True)
    files = sorted(glob.glob(os.path.join(tmp, '*.png')))
    keyed = []
    for i, f in enumerate(files):
        im = Image.open(f).convert('RGB')
        arr = np.array(im)
        u = np.array(pp.remove(im, session=pp.SESSION).convert('RGBA'))[:, :, 3].astype(np.float32) / 255.0
        m = u > 0.4
        # 字幕笔画清除：开运算抹掉细于 ~8px 的白色字幕笔画（浣熊四肢远宽于此）
        disk4 = np.zeros((9, 9), bool)
        dy, dx = np.mgrid[-4:5, -4:5]
        disk4[dy*dy + dx*dx <= 16] = True
        m = ndimage.binary_opening(m, structure=disk4)
        lab, n = ndimage.label(m)
        keep = np.zeros_like(m)
        if n > 0:
            sizes = np.array(ndimage.sum_labels(np.ones_like(lab), lab, np.arange(1, n+1)), dtype=np.float64)
            j = int(np.argmax(sizes))
            keep = lab == j+1
        soft = u * keep
        solid = ndimage.binary_fill_holes(soft > 0.5)
        soft = np.maximum(soft, solid.astype(np.float32)*0.9)
        alpha = np.clip(ndimage.gaussian_filter(soft, 0.8), 0, 1)
        a = (alpha*255).astype(np.uint8)[..., None]
        a[:3]=0; a[-3:]=0; a[:,:3]=0; a[:,-3:]=0
        mk = a[...,0] < 8
        arr2 = arr.copy(); arr2[mk] = 0; a[mk] = 0
        keyed.append(Image.fromarray(np.concatenate([arr2, a], axis=2), 'RGBA'))
        if i % 60 == 0: print('  %d/%d' % (i, len(files)), flush=True)
    shutil.rmtree(tmp, ignore_errors=True)
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
print('== laugh 段抠像 (t=%g-%gs) ==' % (SS_LAUGH, SS_LAUGH+DUR_LAUGH), flush=True)
laugh_n = extract(SS_LAUGH, DUR_LAUGH, os.path.join(ASSET, 'laugh'))
print('== sing 段抠像 (t=%g-%gs) ==' % (SS_SING, SS_SING+DUR_SING), flush=True)
sing_n = extract(SS_SING, DUR_SING, os.path.join(ASSET, 'sing'))

idle = Image.open(os.path.join(ASSET, 'laugh', '0000.png'))
idle.save(os.path.join(ASSET, 'idle.png'))
os.makedirs(os.path.join(ASSET, 'look'), exist_ok=True)
for i in range(2):
    idle.save(os.path.join(ASSET, 'look', f'{i:02d}.png'))
for bank in (0, 1):
    os.makedirs(os.path.join(ASSET, 'blink', str(bank)), exist_ok=True)
    for i in range(2):
        idle.save(os.path.join(ASSET, 'blink', str(bank), f'{i:02d}.png'))

os.makedirs(os.path.join(PET_DIR, 'music'), exist_ok=True)
shutil.copyfile(os.path.join(pp.SRC, 'mat_hx_song.m4a'), os.path.join(PET_DIR, 'music', '我真的特别爱你.m4a'))

meta = {
    "width": 640, "height": 960, "fps": 15.0, "frames": laugh_n,
    "eyeFrames": 2, "blinkFrames": 2, "blinkFps": 15,
    "name": "小浣熊", "id": "hx", "minimal": 1, "laughLabel": "跳一段（双击）",
    "idleRect": {"x": 0.2, "y": 0.35, "w": 0.6, "h": 0.65},
    "poke": {"x": 320, "y": 700, "rx": 85, "ry": 85},
    "warp": {"top": 500, "bottom": 930, "rx": 150, "ry": 60},
    "icon": {"x": 250, "y": 450, "w": 160, "h": 160},
    "sing": {"frames": sing_n, "fps": FPS},
    "idleSeq": "laugh",
    "songSeqs": {"我真的特别爱你.m4a": "sing"},
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

with open(os.path.join(PET_DIR, '使用说明.txt'), 'w', encoding='utf-8') as f:
    f.write('''小浣熊桌宠 · 使用说明

双击「浣熊桌宠.exe」启动（需与 素材.nwp 同目录）。
可与其他桌宠同时运行，互不干扰。

── 交互 ──
1. 待机：小浣熊随《落泪DJ》舞动（动态待机，与原视频同速）
2. 双击：另一段舞蹈演出
3. 拖动/甩飞/全屏隐藏：通用桌宠行为

── 右键菜单 ──
♪ 我真的特别爱你：播放/暂停背景音乐（《落泪DJ》完整版）
音频：切换背景音乐曲目（把更多音频放进 music/ 重启即可）
退出小浣熊

── 数据位置 ──
%LOCALAPPDATA%\\NaiwaDesktopPet-hx\\
''')
print('使用说明已写', flush=True)
print('全部完成，用时 %.0f s' % (time.time()-t0), flush=True)
