import os, sys, glob, shutil, math, json, zipfile, time
import numpy as np
from scipy import ndimage
from PIL import Image
import importlib.util

spec = importlib.util.spec_from_file_location('pp', r'C:/Users/admin/Desktop/MyPet/工具/预处理.py')
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)

# 奶蛙家族套装：从官方族谱图逐成员抠像 → 静态待机 + 程序化 Q弹 双击动画
ROSTER = os.path.join(pp.SRC, '奶蛙家族族谱原图.png')
ROOT_PETS = pp.ROOT

# (PetId, 名称, 族谱裁剪框 l,t,r,b)
MEMBERS = [
    ('naidan',  '奶蛋',       (0, 260, 145, 415)),
    ('xiaonaiwa','小奶蛙',     (335, 245, 480, 400)),
    ('naidou',  '奶豆',       (330, 460, 470, 612)),
    ('naigou',  '奶狗',       (680, 460, 830, 625)),
    ('naifen',  '奶粉',       (15, 630, 135, 840)),
    ('naiji',   '奶鸡',       (310, 685, 465, 845)),
    ('naimao',  '奶猫',       (595, 685, 765, 830)),
    ('naishi',  '奶屎',       (0, 845, 155, 1020)),
    ('dounai',  '豆奶',       (310, 860, 440, 1085)),
    ('naiyu',   '奶鱼',       (840, 850, 1000, 1070)),
    ('naicha',  '奶茶',       (318, 1040, 455, 1194)),
    ('naiping', '奶瓶',       (590, 1040, 700, 1194)),
    ('xigma',   '西格玛奶蛙', (828, 1038, 1000, 1194)),
]

def cutout(roster, box):
    arr = np.array(roster.crop(box).convert('RGB'))
    H, W = arr.shape[:2]
    r_, g_, b_ = arr[...,0].astype(int), arr[...,1].astype(int), arr[...,2].astype(int)
    lum = (r_+g_+b_)/3.0
    mx = np.maximum(np.maximum(r_,g_),b_); mn = np.minimum(np.minimum(r_,g_),b_)
    sat = np.where(mx>0, (mx-mn)/np.maximum(mx,1), 0)
    bg = (lum > 222) & (sat < 0.20)
    alpha = (~bg).astype(np.float32)
    # 最大连通域 = 主体
    lab, n = ndimage.label(alpha > 0.5)
    if n > 0:
        sizes = np.array(ndimage.sum_labels(np.ones_like(lab), lab, np.arange(1, n+1)), dtype=np.float64)
        j = int(np.argmax(sizes))
        comp = lab == j+1
        comp = ndimage.binary_fill_holes(comp)
        alpha = comp.astype(np.float32)
    am = ndimage.gaussian_filter(alpha, 0.8)
    a = (np.clip(am, 0, 1) * 255).astype(np.uint8)[..., None]
    a[:8] = 0; a[-8:] = 0; a[:, :8] = 0; a[:, -8:] = 0  # 裁剪边缘邻格笔画清除
    mk = a[..., 0] < 8
    arr2 = arr.copy(); arr2[mk] = 0; a[mk] = 0
    return Image.fromarray(np.concatenate([arr2, a], axis=2), 'RGBA')

def trim(im, pad=6):
    bb = im.getbbox()
    if not bb: return im
    x0, y0, x1, y1 = bb
    x0 = max(0, x0-pad); y0 = max(0, y0-pad)
    x1 = min(im.width, x1+pad); y1 = min(im.height, y1+pad)
    return im.crop((x0, y0, x1, y1))

def bounce_frames(cut, iw, ih, n=26, fps=15):
    """Q弹：挤压-拉伸衰减振荡，底部锚定，首帧=静止，尾帧≈静止（可无缝循环）"""
    frames = []
    for i in range(n):
        t = i / fps
        k = 0.24 * math.exp(-3.2*t) * math.cos(13*t)
        sw, sh = max(2, round(iw*(1+k))), max(2, round(ih/(1+k)))
        f = Image.new('RGBA', (pp.CANVAS_W, pp.CANVAS_H), (0, 0, 0, 0))
        im = cut.resize((sw, sh), Image.LANCZOS)
        f.paste(im, ((pp.CANVAS_W-sw)//2, pp.CANVAS_H-sh), im)
        frames.append(f)
    return frames

def build(pid, name, box):
    pet_dir = os.path.join(ROOT_PETS, name + '桌宠')
    asset = os.path.join(pet_dir, '资产')
    roster = Image.open(ROSTER).convert('RGB')
    cut = trim(Image.open(os.path.join(r'C:/Users/admin/Desktop/MyPet/素材-通透/family_cutouts', f'{name}.png')).convert('RGBA'))
    os.makedirs(asset, exist_ok=True)
    sc = min(560/cut.width, 620/cut.height, 3.0)
    iw, ih = round(cut.width*sc), round(cut.height*sc)
    laugh_dir = os.path.join(asset, 'laugh')
    os.makedirs(laugh_dir, exist_ok=True)
    for old in glob.glob(os.path.join(laugh_dir, '*.png')):
        os.remove(old)
    frames = bounce_frames(cut, iw, ih)
    for i, f in enumerate(frames):
        f.save(os.path.join(laugh_dir, f'{i:04d}.png'))
    laugh_n = len(frames)
    cut.save(os.path.join(asset, 'idle.png'))
    idle = Image.new('RGBA', (pp.CANVAS_W, pp.CANVAS_H), (0, 0, 0, 0))
    resized = cut.resize((iw, ih), Image.LANCZOS)
    idle.paste(resized, ((pp.CANVAS_W-iw)//2, pp.CANVAS_H-ih), resized)
    idle.save(os.path.join(asset, 'idle.png'))
    os.makedirs(os.path.join(asset, 'look'), exist_ok=True)
    for i in range(2):
        idle.save(os.path.join(asset, 'look', f'{i:02d}.png'))
    for bank in (0, 1):
        os.makedirs(os.path.join(asset, 'blink', str(bank)), exist_ok=True)
        for i in range(2):
            idle.save(os.path.join(asset, 'blink', str(bank), f'{i:02d}.png'))
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
    # 画布几何由 idle 实测
    bb = idle.getbbox()
    ix0, iy0, ix1, iy1 = bb
    meta = {
        "width": 640, "height": 960, "fps": 15.0, "frames": laugh_n,
        "eyeFrames": 2, "blinkFrames": 2, "blinkFps": 15,
        "name": name, "id": pid, "minimal": 1,
        "laughLabel": name + "跳一下（双击）",
        "idleRect": {"x": round(ix0/640, 3), "y": round(iy0/960, 3),
                      "w": round((ix1-ix0)/640, 3), "h": round((iy1-iy0)/960, 3)},
        "poke": {"x": (ix0+ix1)//2, "y": (iy0+iy1)//2, "rx": (ix1-ix0)//4, "ry": (iy1-iy0)//4},
        "warp": {"top": iy0+40, "bottom": iy1-10, "rx": (ix1-ix0)//3, "ry": 60},
        "icon": {"x": ix0, "y": iy0, "w": min(200, ix1-ix0), "h": min(200, iy1-iy0)},
        "sing": {"frames": sing_n, "fps": 15},
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
    print('  [%s] laugh=%d sing=%d -> %s' % (name, laugh_n, sing_n, pet_dir), flush=True)

t0 = time.time()
for pid, name, box in MEMBERS:
    print('== %s ==' % name, flush=True)
    build(pid, name, box)
print('家族套装构建完成，用时 %.0f s' % (time.time()-t0), flush=True)
