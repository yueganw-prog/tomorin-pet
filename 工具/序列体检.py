#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""序列体检：扫描一个动作/唱歌序列文件夹，量化虚影、闪烁、孤立残留三类问题。

用法: python 序列体检.py [序列文件夹]     (默认: 资产/qn)

指标（逐帧）:
  ghost  虚影像素   alpha 处于 40-200 的半透明像素数——虚影/拖尾的主要载体
  flick  帧间闪烁   与上一帧 alpha 的平均绝对差（双方可见区）——逐帧抠像抖动的度量
  resid  孤立残留   alpha>40 但不属于最大连通域的像素数——背景碎块
判定:  ghost/solid > 8%  或  flick > 8  或  resid > 300  → 该帧 [!]
输出:  最差 10 帧摘要 + 总体结论 + 最差 3 帧拼图 <序列名>_体检.png
"""
import sys, os, glob
import numpy as np
from scipy import ndimage
from PIL import Image

folder = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '凑企鹅', '资产', 'qn')
files = sorted(f for f in glob.glob(os.path.join(folder, '*.png')) if not f.endswith('_体检.png'))
if not files:
    print('无 PNG 帧:', folder); sys.exit(1)
name = os.path.basename(folder.rstrip('\\/'))

rows = []
prev = None
for i, f in enumerate(files):
    a = np.array(Image.open(f).convert('RGBA'))[:, :, 3].astype(np.int16)
    solid = int((a > 200).sum())
    ghost = int(((a >= 40) & (a <= 200)).sum())
    resid = 0
    mask = a > 40
    if mask.any():
        lab, n = ndimage.label(mask)
        if n > 1:
            sizes = ndimage.sum_labels(np.ones_like(lab), lab, range(1, n + 1))
            resid = int(mask.sum() - sizes.max())
    flick = 0.0
    if prev is not None:
        m = (a > 40) | (prev > 40)
        if m.any():
            flick = float(np.abs(a - prev)[m].mean())
    rows.append((i, ghost, solid, flick, resid))
    prev = a

def median(vals):
    v = sorted(vals); n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2

med_ghost_ratio = median([r[1] / max(r[2], 1) for r in rows])
med_flick = median([r[3] for r in rows])
med_resid = median([r[4] for r in rows])
# 离群判定：相对本序列中位数的尖峰才有意义（快动作序列的 flick / 合法分离件不误报）
flick_thr = 3 * med_flick + 2 if med_flick < 5 else float('inf')  # 快动作序列 flick 不可诊断
ghost_thr = max(0.08, 3 * med_ghost_ratio)
resid_thr = max(300, 3 * med_resid)

def flag(r):
    _, ghost, solid, flick, resid = r
    return (solid > 0 and ghost / max(solid, 1) > ghost_thr) or flick > flick_thr or resid > resid_thr

flagged = [r for r in rows if flag(r)]
rows.sort(key=lambda r: -(r[1] / max(r[2], 1) + r[3] / max(flick_thr, 1) + r[4] / max(resid_thr, 1)))
print(f'序列 {name}: {len(rows)} 帧 | 标[!] {len(flagged)} 帧')
print('最差 10 帧 (帧号 ghost ghost/solid flick resid):')
for r in rows[:10]:
    print('  #%04d  ghost=%5d  g/s=%5.1f%%  flick=%5.2f  resid=%5d  %s' % (
        r[0], r[1], 100 * r[1] / max(r[2], 1), r[3], r[4], '[!]' if flag(r) else ''))
tot_ghost = sum(r[1] for r in rows); tot_solid = sum(r[2] for r in rows)
max_flick = max(r[3] for r in rows); tot_resid = sum(r[4] for r in rows)
print('总体: 虚影占比 %.1f%% | 最大帧间闪烁 %.2f | 孤立残留合计 %d' % (
    100 * tot_ghost / max(tot_solid, 1), max_flick, tot_resid))
print('基线(中位): g/s=%.1f%% flick=%.2f resid=%d → 阈值: g/s>%.0f%% flick>%.1f resid>%d' % (
    100 * med_ghost_ratio, med_flick, med_resid, 100 * ghost_thr, flick_thr, resid_thr))
if not flagged:
    print('结论: PASS —— 无需返工')
else:
    print('结论: %d 帧离群，建议用审计拼图人工确认' % len(flagged))

# 最差 3 帧拼图
worst = [r[0] for r in rows[:3]]
sheet = Image.new('RGB', (320 * len(worst), 480), (30, 30, 34))
for j, idx in enumerate(worst):
    im = Image.open(files[idx]).convert('RGBA').resize((320, 480))
    bg = Image.new('RGBA', (320, 480)); px = bg.load()
    for y in range(0, 480, 16):
        for x in range(0, 320, 16):
            c = (70, 70, 76, 255) if (x // 16 + y // 16) % 2 else (52, 52, 58, 255)
            for dy in range(16):
                for dx in range(16):
                    if x + dx < 320 and y + dy < 480: px[x + dx, y + dy] = c
    bg.alpha_composite(im)
    sheet.paste(bg.convert('RGB'), (j * 320, 0))
import tempfile
sheet.save(os.path.join(tempfile.gettempdir(), f'{name}_体检.png'))
print('最差帧拼图:', os.path.join(tempfile.gettempdir(), f'{name}_体检.png'))
