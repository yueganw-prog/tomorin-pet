#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""凑企鹅桌宠素材预处理流水线。

画布统一 640×960（站立图等比缩放填满，动作帧底部居中合成）。
阶段: idle / sing / laugh / pack   (python 预处理.py <stage>)
"""
import io, json, os, subprocess, sys, zipfile
import glob, shutil, tempfile
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from rembg import remove, new_session

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "素材-通透")
OUT = os.path.join(ROOT, "凑企鹅", "资产")
CANVAS_W, CANVAS_H = 640, 960
IDLE_SCALE = 0.46          # 站立图在画布中的占比（贴底居中），与通透头部等高
IDLE_TRANSFORM = [1.0, 0.0, 0.0]  # pack 阶段换算 poke/warp/icon 用：scale, offset_x, offset_y
EYES = [(176, 281, 257, 352), (350, 281, 431, 352)]  # 站立图源分辨率下的双眼框（含完整轮廓）
IDLE_SRC_CROP_H = 950

# 通透视频：裁剪框（避开标题/字幕/水印），标题残影清除带（裁剪坐标系）
TT_CROP = (150, 55, 780, 640)          # 630×585
TT_TITLE_ERASE = (0, 0, 400, 30)       # 裁剪坐标内抹掉标题残影
# sing 绿幕：裁剪框（避开右上水印）
SG_CROP = (760, 66, 1220, 1080)        # 460×1014
SG_SECONDS, SG_FPS = 60, 15

SESSION = new_session("u2net")  # 三模型实测最优：云雾/枯树/栈道全干净，0.3s/帧（bria 20s/帧太慢）


def ffmpeg_frames(video, fps=None, seconds=None):
    """ffmpeg 抽帧到临时目录 → 返回 (临时目录, 文件列表)；调用方负责 shutil.rmtree"""
    import tempfile, glob
    tmp = tempfile.mkdtemp(prefix="petframes_")
    cmd = ["ffmpeg", "-v", "error", "-i", video]
    if seconds is not None:
        cmd += ["-t", str(seconds)]
    if fps is not None:
        cmd += ["-vf", f"fps={fps}"]
    cmd += [os.path.join(tmp, "%05d.png")]
    subprocess.run(cmd, capture_output=True, check=True)
    return tmp, sorted(glob.glob(os.path.join(tmp, "*.png")))


def chroma_key(im):
    """绿幕抠图：绿色系→透明，轻去溢色"""
    a = np.array(im).astype(np.int16)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    green = (g > 130) & (g > 1.32 * r) & (g > 1.32 * b)
    a[:, :, 3] = np.where(green, 0, 255)
    spill = (~green) & (g > r) & (g > b)          # 边缘绿溢出压回
    a[:, :, 1] = np.where(spill, np.maximum(r, b), g)
    return Image.fromarray(a.astype(np.uint8))


def strip_below_body(im, min_width=100, margin=6):
    """砍掉身体底缘以下的残留（原视频里企鹅是举在杆子上的纸偶，
    杆子和身体像素相连，连通域清洗删不掉；身体底缘=最后一行宽度≥min_width 的行）"""
    a = np.array(im)
    op = a[:, :, 3] > 24
    widths = op.sum(axis=1)
    ys = np.where(widths >= min_width)[0]
    if len(ys):
        base = ys.max()
        if base < a.shape[0] - margin:
            a[base + margin:, :, 3] = 0
    return Image.fromarray(a)


def remove_green(im):
    """清除绿色系残留（背景树丛），企鹅配色里没有绿色"""
    a = np.array(im).astype(np.int16)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    green = (g > 60) & (g > r + 15) & (g > b + 15)
    a[green, 3] = 0
    return Image.fromarray(a.astype(np.uint8))


def clean_alpha(im, keep_ratio=.08, min_alpha=30):
    """抠图后处理：压掉低透明度残影，只保留较大的连通区域（企鹅主体），
    丢掉背景残渣（树枝/条纹/文字残影等小碎块）。"""
    a = np.array(im)
    alpha = a[:, :, 3]
    alpha[alpha < min_alpha] = 0
    mask = alpha > 0
    if mask.any():
        labels, n = ndimage.label(mask)
        if n > 1:
            sizes = ndimage.sum_labels(np.ones_like(labels), labels, range(1, n + 1))
            biggest = sizes.max()
            keep = np.zeros(n + 1, bool)
            keep[1:] = sizes >= biggest * keep_ratio
            a[:, :, 3] = np.where(keep[labels], alpha, 0)
    else:
        a[:, :, 3] = 0
    return Image.fromarray(a)


def compose_bottom(frame, cx=None, bottom_margin=0):
    """按当前尺寸贴到画布底部居中，返回画布 Image"""
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    x = (CANVAS_W - frame.width) // 2 if cx is None else cx - frame.width // 2
    canvas.paste(frame, (x, CANVAS_H - frame.height - bottom_margin), frame)
    return canvas


def stage_idle():
    """tomorin1.png → 裁掉底部水印残片 → 缩小贴底居中（IDLE_SCALE）"""
    im = Image.open(os.path.join(SRC, "tomorin1.png")).convert("RGBA")
    im = im.crop((0, 0, im.width, 950))
    full_w, full_h = CANVAS_W, round(im.height * CANVAS_W / im.width)
    w, h = round(full_w * IDLE_SCALE), round(full_h * IDLE_SCALE)
    im = im.resize((w, h), Image.LANCZOS)
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    ox, oy = (CANVAS_W - w) // 2, CANVAS_H - h
    canvas.paste(im, (ox, oy), im)
    IDLE_TRANSFORM[0], IDLE_TRANSFORM[1], IDLE_TRANSFORM[2] = IDLE_SCALE, ox, oy
    with open(os.path.join(OUT, "idle_transform.json"), "w") as fh:
        json.dump({"scale": IDLE_SCALE, "ox": ox, "oy": oy}, fh)
    os.makedirs(OUT, exist_ok=True)
    canvas.save(os.path.join(OUT, "idle.png"))
    print(f"idle 完成 缩放{IDLE_SCALE} 偏移({ox},{oy})", canvas.size)


def synthesize_blink(im, openness):
    """在站立图上合成闭眼帧：整个眼框用额头皮肤填充（覆盖完整原轮廓），
    再画一条随闭合微微下移的睫毛弧线（动漫式闭眼）。openness>=1 返回原图。"""
    if openness >= 1:
        return im
    a = np.array(im).astype(np.int16)
    for (x0, y0, x1, y1) in EYES:
        band = a[y0 - 18:y0 - 4, x0:x1].reshape(-1, 3)
        bright = band[band.sum(axis=1) > 420]
        gs = np.median(bright if len(bright) else band, axis=0)
        for x in range(x0, x1):
            col = a[y0 - 18:y0 - 4, x]
            br = col[col.sum(axis=1) > 420]
            a[y0:y1, x] = np.median(br, axis=0) if len(br) else gs
    im = Image.fromarray(a.astype(np.uint8))
    SS = 2
    big = im.resize((im.width * SS, im.height * SS), Image.LANCZOS)
    d = ImageDraw.Draw(big)
    for (x0, y0, x1, y1) in EYES:
        h = y1 - y0
        arc_y = (y0 + h * (0.62 - 0.10 * openness)) * SS
        d.arc([x0 * SS, arc_y - 6 * SS, x1 * SS, arc_y + 12 * SS], start=25, end=155,
              fill=(74, 58, 58, 255), width=4 * SS)
    return big.resize((im.width, im.height), Image.LANCZOS)


def compose_idle_frame(src):
    """站立源图 → 画布合成（与 stage_idle 相同变换）"""
    im = src.crop((0, 0, src.width, IDLE_SRC_CROP_H))
    full_w, full_h = CANVAS_W, round(im.height * CANVAS_W / im.width)
    w, h = round(full_w * IDLE_SCALE), round(full_h * IDLE_SCALE)
    im = im.resize((w, h), Image.LANCZOS)
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    ox, oy = (CANVAS_W - w) // 2, CANVAS_H - h
    canvas.paste(im, (ox, oy), im)
    return canvas


def stage_actions(only=None):
    """绿幕动作视频（跳舞/飞踢）→ 色键抠图 → union bbox 统一映射（贴底，保留位移轨迹）"""
    def thin_line_removal(im, radius=6):
        """色键后处理：形态学开运算去掉细于 2*radius 的黑线/杂线，主体保留"""
        a = np.array(im)
        mask = a[:, :, 3] > 24
        yy, xx = np.mgrid[-radius:radius + 1, -radius:radius + 1]
        disk = (yy * yy + xx * xx) <= radius * radius
        opened = ndimage.binary_opening(mask, structure=disk)
        a[:, :, 3] = np.where(opened, a[:, :, 3], 0)
        return Image.fromarray(a)
    def chroma(im):
        a = np.array(im).astype(np.int16)
        r, g, b = a[:,:,0], a[:,:,1], a[:,:,2]
        green = (g>130)&(g>1.32*r)&(g>1.32*b)
        a[:,:,3] = np.where(green, 0, 255)
        spill = (~green)&(g>r)&(g>b)
        a[:,:,1] = np.where(spill, np.maximum(r,b), g)
        return thin_line_removal(Image.fromarray(a.astype(np.uint8)))
    jobs = [
        # (名称, 视频, fps, 目标高度, 抠图方式, 是否导出音频, 起始秒, 时长秒, 源预裁剪比例(l,t,r,b)或None, 音频起始秒, 音频时长秒)
        ("dance", os.path.join(SRC, "mat_dance43.mp4"), 15, 600, "green", True, None, None, None, None, None),
        ("jump",  os.path.join(SRC, "jump.mp4"),        30, 560, "green", True, None, None, None, None, None),
        ("turn",  os.path.join(SRC, "mat_turn.mp4"),   15, 600, "green", False, None, None, None, None, None),
        ("hungry",os.path.join(SRC, "mat_qq.mp4"),     30, 620, "rembg", True, 35.4, 1.8, (0.0, 0.0, 1.0, 0.92), 37.15, 1.5),
        ("mic",   os.path.join(SRC, "mat_sing58.mp4"), 12, 620, "rembg", False, 1.25, 20.0, None, None, None),
        ("closeup", os.path.join(SRC, "mat_long.mp4"), 12, 620, "green", False, 60.0, 20.0, None, None, None),
        ("yuai",  os.path.join(SRC, "mat_yuai87.mp4"), 12, 620, "rembg", False, 44.0, 16.0, None, None, None),
        ("qn",    os.path.join(SRC, "mat_qn_BV1ih.mp4"), 12, 620, "rembg", False, 62.0, 20.0, (0.18, 0.26, 0.80, 1.0), None, None),
    ]
    if only: jobs = [j for j in jobs if j[0] in only]
    for name, video, fps, target_h, mode, want_wav, ss, dur, crop, a_ss, a_dur in jobs:
        if not os.path.exists(video):
            print("跳过(缺视频):", name, flush=True); continue
        tmp = tempfile.mkdtemp(prefix="act_")
        cmd = ["ffmpeg","-v","error","-i",video]
        if ss is not None: cmd += ["-ss",str(ss)]
        if dur is not None: cmd += ["-t",str(dur)]
        if crop is not None:
            cmd += ["-vf","crop=iw*{0}:ih*{1}:iw*{2}:ih*{3}".format(crop[2]-crop[0],crop[3]-crop[1],crop[0],crop[1])]
        cmd += ["-r",str(fps),"-f","image2",os.path.join(tmp,"%05d.png")]
        subprocess.run(cmd,capture_output=True,check=True)
        files = sorted(glob.glob(os.path.join(tmp,"*.png")))
        keyed = []
        for f in files:
            im = Image.open(f).convert("RGBA")
            keyed.append(chroma(im) if mode=="green" else clean_alpha(remove(im, session=SESSION)))
        shutil.rmtree(tmp, ignore_errors=True)
        x0=y0=10**9; x1=y1=-1
        for k in keyed:
            bb = k.getbbox()
            if bb:
                x0=min(x0,bb[0]); y0=min(y0,bb[1]); x1=max(x1,bb[2]); y1=max(y1,bb[3])
        uw, uh = x1-x0, y1-y0
        s = min(target_h/uh, CANVAS_W*0.9/uw, 1.15)
        sw, sh = round(uw*s), round(uh*s)
        os.makedirs(os.path.join(OUT,name), exist_ok=True)
        for old in glob.glob(os.path.join(OUT,name,"*.png")):  # 清掉上一轮的多余帧
            os.remove(old)
        for i,k in enumerate(keyed):
            crop = k.crop((x0,y0,x1,y1)).resize((sw,sh), Image.LANCZOS)
            canvas = Image.new("RGBA",(CANVAS_W,CANVAS_H),(0,0,0,0))
            canvas.paste(crop,((CANVAS_W-sw)//2, CANVAS_H-sh),crop)
            canvas.save(os.path.join(OUT,name,f"{i:04d}.png"))
        if want_wav:
            acmd = ["ffmpeg","-y","-v","error","-i",video]
            if a_ss is not None: acmd += ["-ss",str(a_ss)]
            if a_dur is not None: acmd += ["-t",str(a_dur)]
            acmd += ["-vn","-acodec","pcm_s16le","-ar","44100","-ac","2",os.path.join(OUT,f"{name}.wav")]
            subprocess.run(acmd,check=True)
        print(name,"完成",len(keyed),"帧 union",(uw,uh),"scale",round(s,2),flush=True)


def stage_blink(only_audit=False):
    """合成 7 帧眨眼 × 两个注视组，画布尺寸输出"""
    src = Image.open(os.path.join(SRC, "tomorin1.png")).convert("RGBA")
    openness = [1.0, .55, .15, .0, .15, .55, 1.0]
    for bank in (0, 1):
        os.makedirs(os.path.join(OUT, "blink", str(bank)), exist_ok=True)
        for i, o in enumerate(openness):
            frame = compose_idle_frame(synthesize_blink(src, o))
            if only_audit:
                frame.save(os.path.join(SRC, f"blink_audit_{i}.png"))
            else:
                frame.save(os.path.join(OUT, "blink", str(bank), f"{i:02d}.png"))
    print("blink 完成 7 帧 × 2 组" if not only_audit else "blink 预览已导出")


def stage_postclean():
    """对已生成的 laugh 帧做完整清洗：连通域 + 底缘砍杆 + 去绿"""
    folder = os.path.join(OUT, "laugh")
    files = sorted(f for f in os.listdir(folder) if f.endswith(".png"))
    for i, f in enumerate(files):
        p = os.path.join(folder, f)
        im = clean_alpha(Image.open(p).convert("RGBA"))
        im = remove_green(im)
        im = strip_below_body(im)
        im.save(p)
        if i % 100 == 0:
            print(f"  {i}/{len(files)}", flush=True)
    print("postclean 完成", len(files), "帧")


def stage_laugh(only_audit=False):
    """通透视频 → 裁剪 → rembg → 清文字 → 底部合成；同时导出音频"""
    import shutil
    video = os.path.join(SRC, "通透参考.mp4")
    tmp, files = ffmpeg_frames(video)
    print(f"通透: 共 {len(files)} 帧", flush=True)
    os.makedirs(os.path.join(OUT, "laugh"), exist_ok=True)
    audit = []
    cw, ch = TT_CROP[2] - TT_CROP[0], TT_CROP[3] - TT_CROP[1]
    sw, sh = CANVAS_W, round(ch * CANVAS_W / cw)
    for i, f in enumerate(files):
        if only_audit and i % 70 != 0:
            continue
        im = Image.open(f).convert("RGBA")
        crop = im.crop(TT_CROP)
        cut = remove(crop, session=SESSION)
        arr = np.array(cut)
        x0, y0, x1, y1 = TT_TITLE_ERASE
        arr[y0:y1, x0:x1, 3] = 0
        cut = Image.fromarray(arr).resize((sw, sh), Image.LANCZOS)
        cut = clean_alpha(cut)
        canvas = compose_bottom(cut)
        if only_audit and i % 70 == 0:
            audit.append(canvas.copy())
        if not only_audit:
            canvas.save(os.path.join(OUT, "laugh", f"{i:04d}.png"))
        if i % 50 == 0:
            print(f"  {i}/{len(files)}", flush=True)
    shutil.rmtree(tmp, ignore_errors=True)
    if only_audit:
        sheet = Image.new("RGB", (CANVAS_W // 2 * len(audit), CANVAS_H // 2), (38, 38, 46))
        for j, a in enumerate(audit):
            sheet.paste(a.resize((CANVAS_W // 2, CANVAS_H // 2), Image.LANCZOS), (j * CANVAS_W // 2, 0))
        sheet.save(os.path.join(SRC, "laugh_audit.jpg"), quality=85)
        print("audit sheet saved")
        return
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video, "-vn",
                    "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                    os.path.join(OUT, "通透.wav")], check=True)
    print("laugh 完成", len(files), "帧 + 通透.wav")


def stage_sing(only_audit=False):
    """sing.mp4 前 60s → 15fps → 绿幕抠图 → 底部合成循环序列"""
    import shutil
    tmp, files = ffmpeg_frames(os.path.join(SRC, "sing.mp4"), fps=SG_FPS, seconds=SG_SECONDS)
    print(f"sing: 共 {len(files)} 帧", flush=True)
    os.makedirs(os.path.join(OUT, "sing"), exist_ok=True)
    cw, ch = SG_CROP[2] - SG_CROP[0], SG_CROP[3] - SG_CROP[1]
    sh = CANVAS_H
    sw = round(cw * sh / ch)
    audit = []
    for i, f in enumerate(files):
        im = Image.open(f).convert("RGBA")
        crop = chroma_key(im.crop(SG_CROP)).resize((sw, sh), Image.LANCZOS)
        canvas = compose_bottom(crop)
        if only_audit and i % 60 == 0:
            audit.append(canvas.copy())
        if not only_audit:
            canvas.save(os.path.join(OUT, "sing", f"{i:04d}.png"))
    shutil.rmtree(tmp, ignore_errors=True)
    if only_audit:
        sheet = Image.new("RGB", (CANVAS_W // 2 * len(audit), CANVAS_H // 2), (38, 38, 46))
        for j, a in enumerate(audit):
            sheet.paste(a.resize((CANVAS_W // 2, CANVAS_H // 2), Image.LANCZOS), (j * CANVAS_W // 2, 0))
        sheet.save(os.path.join(SRC, "sing_audit.jpg"), quality=85)
        print("audit sheet saved")


def stage_pack():
    """打包 素材.nwp + 元数据（眨眼/转眼用 idle 占位，无素材暂不做）"""
    laugh_n = len([f for f in os.listdir(os.path.join(OUT, "laugh")) if f.endswith(".png")])
    sing_n = len([f for f in os.listdir(os.path.join(OUT, "sing")) if f.endswith(".png")])
    def dircount(name):
        p = os.path.join(OUT, name)
        return len([f for f in os.listdir(p) if f.endswith(".png")]) if os.path.isdir(p) else 0
    dance_n, jump_n = dircount("dance"), dircount("jump")
    # 动作序列元数据：帧数不足 2 的文件夹自动跳过（删除动作后无需改代码）
    seqs_meta = {}
    for seq_name, seq_fps in (("dance", 15), ("jump", 30), ("mic", 12), ("turn", 15), ("closeup", 12), ("yuai", 12), ("qn", 12), ("pyj", 15), ("hungry", 30)):
        n_ = dircount(seq_name)
        if n_ >= 2:
            seqs_meta[seq_name] = {"frames": n_, "fps": seq_fps}
    # 身体区域按站立图缩放换算（跨进程：从 idle_transform.json 读取）
    tf_path = os.path.join(OUT, "idle_transform.json")
    if os.path.exists(tf_path):
        with open(tf_path) as fh:
            tf = json.load(fh)
        IDLE_TRANSFORM[0], IDLE_TRANSFORM[1], IDLE_TRANSFORM[2] = tf["scale"], tf["ox"], tf["oy"]
    s, ox, oy = IDLE_TRANSFORM
    def tp(x, y): return (round(x * s + ox), round(y * s + oy))
    poke = (*tp(318, 627), 137 * s, 202 * s)
    warp = (round(430 * s + oy), round(940 * s + oy), 200 * s, 190 * s)
    icon = (*tp(180, 70), round(320 * s), round(320 * s))
    meta = {
        "width": CANVAS_W, "height": CANVAS_H, "fps": 30.0, "frames": laugh_n,
        "eyeFrames": 11, "blinkFrames": 7, "blinkFps": 30,
        "name": "凑企鹅", "id": "tomorin", "soundFile": "通透.wav",
        "poke": {"x": poke[0], "y": poke[1], "rx": round(poke[2]), "ry": round(poke[3])},
        "warp": {"top": warp[0], "bottom": warp[1], "rx": round(warp[2]), "ry": round(warp[3])},
        "icon": {"x": icon[0], "y": icon[1], "w": icon[2], "h": icon[3]},
        "idleRect": {"x": round(ox / CANVAS_W, 3), "y": round(oy / CANVAS_H, 3),
                      "w": round((CANVAS_W - 2 * ox) / CANVAS_W, 3), "h": round((CANVAS_H - oy) / CANVAS_H, 3)},
        "sing": {"frames": sing_n, "fps": SG_FPS},
        "dance": seqs_meta.get("dance"),
        "jump": seqs_meta.get("jump"),
        "mic": seqs_meta.get("mic"),
        "turn": seqs_meta.get("turn"),
        "closeup": seqs_meta.get("closeup"),
        "yuai": seqs_meta.get("yuai"),
        "qn": seqs_meta.get("qn"),
        "pyj": seqs_meta.get("pyj"),
        "hungry": seqs_meta.get("hungry"),
        # 每首歌绑定专属唱歌视觉：歌名→序列（用户可改）
        "songSeqs": {
            "billie jean.m4a": "dance",
            "cry for me.m4a": "mic",
            "just two of us.m4a": "closeup",
            "L的小曲.m4a": "sing",
            "雨爱.m4a": "yuai",
            "去年夏天.m4a": "qn",
            "朋友的酒.m4a": "pyj",
        },
    }
    nwp = os.path.join(ROOT, "凑企鹅", "素材.nwp")
    with zipfile.ZipFile(nwp, "w", zipfile.ZIP_STORED) as z:
        z.write(os.path.join(OUT, "idle.png"), "idle.png")
        for i in range(11):
            z.write(os.path.join(OUT, "idle.png"), f"look/{i:02d}.png")
        blink_dir = os.path.join(OUT, "blink", "0")
        have_blink = os.path.isdir(blink_dir) and len(os.listdir(blink_dir)) >= 2
        for bank in (0, 1):
            for i in range(7):
                if have_blink:
                    z.write(os.path.join(OUT, "blink", str(bank), f"{i:02d}.png"), f"blink/{bank}/{i:02d}.png")
                else:
                    z.write(os.path.join(OUT, "idle.png"), f"blink/{bank}/{i:02d}.png")
        for i in range(laugh_n):
            z.write(os.path.join(OUT, "laugh", f"{i:04d}.png"), f"laugh/{i:04d}.png")
        for i in range(sing_n):
            z.write(os.path.join(OUT, "sing", f"{i:04d}.png"), f"sing/{i:04d}.png")
        for i in range(dance_n):
            z.write(os.path.join(OUT, "dance", f"{i:04d}.png"), f"dance/{i:04d}.png")
        for i in range(jump_n):
            z.write(os.path.join(OUT, "jump", f"{i:04d}.png"), f"jump/{i:04d}.png")
        mic_n = dircount("mic")
        for i in range(mic_n):
            z.write(os.path.join(OUT, "mic", f"{i:04d}.png"), f"mic/{i:04d}.png")
        for extra in ("turn", "closeup", "yuai", "qn", "pyj", "hungry"):
            n_ = dircount(extra)
            for i in range(n_):
                z.write(os.path.join(OUT, extra, f"{i:04d}.png"), f"{extra}/{i:04d}.png")
        z.writestr("metadata.json", json.dumps(meta, ensure_ascii=False, indent=1))
    import shutil
    # 副车音频：跟 exe 同目录
    for wav in ("dance.wav", "jump.wav", "hungry.wav"):
        src = os.path.join(OUT, wav)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(os.path.dirname(nwp), wav))
    print(f"pack 完成: {nwp}  laugh={laugh_n} sing={sing_n}")


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    {"idle": stage_idle, "laugh": stage_laugh, "sing": stage_sing, "pack": stage_pack,
     "postclean": stage_postclean, "blink": stage_blink, "actions": stage_actions,
     "actions_only": lambda: stage_actions(tuple(sys.argv[2:])),
     "laugh_audit": lambda: stage_laugh(only_audit=True),
     "sing_audit": lambda: stage_sing(only_audit=True)}[stage]()
