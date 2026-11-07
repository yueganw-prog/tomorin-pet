import os, sys, glob, shutil, time
import numpy as np
from scipy import ndimage
from PIL import Image
import importlib.util

spec = importlib.util.spec_from_file_location('pp', r'C:/Users/admin/Desktop/MyPet/工具/预处理.py')
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)

# 族谱图逐成员 rembg 抠像（单对象分割 = u2net 最可靠场景）
ROSTER = r'C:/Users/admin/Desktop/MyPet/素材-通透/奶蛙家族族谱原图.png'
OUTD = r'C:/Users/admin/Desktop/MyPet/素材-通透/family_cutouts'
os.makedirs(OUTD, exist_ok=True)

MEMBERS = [
    ('奶蛋',       (5, 260, 140, 415)),
    ('小奶蛙',     (335, 245, 480, 400)),
    ('奶豆',       (330, 460, 470, 615)),
    ('奶狗',       (686, 466, 822, 619)),
    ('奶粉',       (20, 630, 135, 840)),
    ('奶鸡',       (283, 640, 472, 835)),
    ('奶猫',       (585, 640, 810, 835)),
    ('奶屎',       (0, 845, 160, 1025)),
    ('豆奶',       (300, 818, 452, 1090)),
    ('奶鱼',       (840, 850, 1000, 1070)),
    ('奶茶',       (318, 1040, 455, 1194)),
    ('奶瓶',       (590, 1040, 700, 1194)),
    ('西格玛奶蛙', (828, 1038, 1000, 1194)),
]

roster = Image.open(ROSTER).convert('RGB')
t0 = time.time()
for i, (name, (l, t, r, b)) in enumerate(MEMBERS):
    crop = roster.crop((l, t, r, b))
    out = pp.remove(crop, session=pp.SESSION)
    a = np.array(out.convert('RGBA'))[:, :, 3].astype(np.float32) / 255.0
    m = a > 0.4
    disk5 = np.zeros((11, 11), bool)
    dy, dx = np.mgrid[-5:6, -5:6]
    disk5[dy*dy + dx*dx <= 25] = True
    m = ndimage.binary_opening(m, structure=disk5)
    lab, n = ndimage.label(m)
    keep = np.zeros_like(m)
    if n > 0:
        sizes = np.array(ndimage.sum_labels(np.ones_like(lab), lab, np.arange(1, n+1)), dtype=np.float64)
        j = int(np.argmax(sizes))
        keep = lab == j+1
    if name == '奶猫':
        a[:62, :70] = 0  # 左上角「奶鸡」标签文字区清除（耳朵在 x660 起不受影响）
    soft = a * keep
    solid = ndimage.binary_fill_holes(soft > 0.5)
    soft = np.maximum(soft, solid.astype(np.float32)*0.9)
    alpha = np.clip(ndimage.gaussian_filter(soft, 0.8), 0, 1)
    aa = (alpha*255).astype(np.uint8)[..., None]
    mk = aa[..., 0] < 8
    arr2 = np.array(crop); arr2[mk] = 0; aa[mk] = 0
    Image.fromarray(np.concatenate([arr2, aa], axis=2), 'RGBA').save(os.path.join(OUTD, f'{name}.png'))
    print('  %s 完成' % name, flush=True)
print('全部抠像完成，用时 %.1f s' % (time.time()-t0), flush=True)

# 审计拼图
cell_w, cell_h = 160, 240
cols = 5
rows = (len(MEMBERS)+cols-1)//cols
sheet = Image.new('RGB', (cell_w*cols, cell_h*rows), (45, 45, 52))
from PIL import ImageDraw, ImageFont
font = ImageFont.truetype(r'C:/Windows/Fonts/msyh.ttc', 16)
d = ImageDraw.Draw(sheet)
for j, (name, _) in enumerate(MEMBERS):
    im = Image.open(os.path.join(OUTD, f'{name}.png')).convert('RGBA')
    bg = Image.new('RGBA', im.size, (60, 60, 68, 255))
    bg.alpha_composite(im)
    sheet.paste(bg.convert('RGB').resize((cell_w, cell_h-24)), ((j%cols)*cell_w, (j//cols)*cell_h+24))
    d.text(((j%cols)*cell_w+6, (j//cols)*cell_h+4), name, font=font, fill=(120, 255, 140))
sheet.save(r'C:/Users/admin/AppData/Local/Temp/roster_cutouts.jpg', quality=88)
print('审计图已存', flush=True)
