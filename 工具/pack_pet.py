#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把你的形象打包成桌宠素材包（素材.nwp）。

最小用法（一张图就能养）:
  python pack_pet.py --idle 我的形象.png --name 小可爱 --id mypet

可选素材:
  --hover 2.png         鼠标悬停时眼睛看的方向（缺省=眼睛不跟鼠标）
  --closed 闭眼.png     用来合成眨眼（缺省=不眨眼）
  --look-frames 目录     11 张转眼帧 00.png..10.png（代替 hover）
  --blink-frames 目录 [目录2]  直接提供眨眼序列帧（7 张左右，两个注视方向）
  --laugh-frames 目录    大笑序列帧（最多 2000 张）
  --laugh-video 视频     用 ffmpeg 抽帧（已检测到系统装有 ffmpeg）
  --laugh-base 图片      程序化生成弹跳式大笑（缺省用 idle）
  --sound 笑声.wav       复制到程序目录，双击大笑时播放
  --fps 30              大笑帧率

身体区域参数（像素，缺省按画面比例自动估算，可在打包后手改 metadata.json）:
  --poke x y rx ry          戳肚子判定椭圆（中心/半径）
  --warp top bottom rx ry   戳肚子变形的上下边界和半径
  --icon x y w h            托盘头像裁剪框（对准脸部）

打包后把生成的 素材.nwp 放到 我的桌宠.exe 旁边即可。
"""
import argparse, io, json, math, os, shutil, subprocess, sys, tempfile, zipfile
from PIL import Image

LOOK_N = 11   # 转眼帧数（代码允许 2~60）
BLINK_N = 7   # 眨眼帧数


def load(path):
    im = Image.open(path)
    im.load()
    return im.convert("RGBA")


def add_png(z, name, im):
    buf = io.BytesIO()
    im.save(buf, "PNG")
    z.writestr(name, buf.getvalue())


def crossfade(base, top, w):
    if w <= 0: return base.copy()
    if w >= 1: return top.copy()
    return Image.blend(base, top, w)


def squash_frame(base, s):
    """以底边为支点压扁/拉伸，s>0 压扁，s<0 拉长。"""
    if abs(s) < 1e-4:
        return base.copy()
    w, h = base.size
    im = base.resize((max(1, round(w * (1 + s * 0.7))), max(1, round(h * (1 - s)))), Image.LANCZOS)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.paste(im, (round((w - im.width) / 2), h - im.height), im)
    return canvas


def dir_frames(path, expect, label):
    files = sorted(f for f in os.listdir(path) if f.lower().endswith(".png"))
    if not files:
        sys.exit(f"错误：{label} 目录里没有 png：{path}")
    return [load(os.path.join(path, f)) for f in files]


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--idle", required=True, help="待机图（必填）")
    ap.add_argument("--hover", help="悬停注视图")
    ap.add_argument("--closed", help="闭眼图（用于合成眨眼）")
    ap.add_argument("--look-frames", help="11 张转眼帧目录")
    ap.add_argument("--blink-frames", nargs="+", help="眨眼帧目录（1 个目录两个方向共用，或给 2 个）")
    ap.add_argument("--laugh-frames", help="大笑帧目录")
    ap.add_argument("--laugh-video", help="大笑视频（ffmpeg 抽帧）")
    ap.add_argument("--laugh-base", help="用单张图生成弹跳大笑")
    ap.add_argument("--sound", help="笑声 wav")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--name", default="小桌宠")
    ap.add_argument("--id", default="mypet", help="唯一 id（小写英文数字），多只桌宠共存时不要重复")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "素材.nwp"))
    ap.add_argument("--poke", nargs=4, type=float, metavar=("X", "Y", "RX", "RY"))
    ap.add_argument("--warp", nargs=4, type=float, metavar=("TOP", "BOTTOM", "RX", "RY"))
    ap.add_argument("--icon", nargs=4, type=float, metavar=("X", "Y", "W", "H"))
    args = ap.parse_args()

    idle = load(args.idle)
    w, h = idle.size
    if not (1 <= w <= 1024 and 1 <= h <= 1024):
        sys.exit(f"错误：图片尺寸 {w}x{h} 超出范围（1~1024）")

    # --- 转眼帧（11 张）---
    if args.look_frames:
        looks = dir_frames(args.look_frames, LOOK_N, "转眼帧")
        if len(looks) < 2 or len(looks) > 60:
            sys.exit(f"错误：转眼帧数量 {len(looks)} 超出范围（2~60）")
    elif args.hover:
        hover = load(args.hover)
        if hover.size != idle.size: sys.exit("错误：hover 与 idle 尺寸不一致")
        looks = [crossfade(idle, hover, i / (LOOK_N - 1)) for i in range(LOOK_N)]
    else:
        looks = [idle.copy() for _ in range(LOOK_N)]

    # --- 眨眼帧（两组：普通注视 / 悬停注视）---
    blink_w = [0.0, 0.4, 0.85, 1.0, 0.85, 0.4, 0.0]
    if args.blink_frames:
        bank0 = dir_frames(args.blink_frames[0], BLINK_N, "眨眼帧")
        bank1 = dir_frames(args.blink_frames[1], BLINK_N, "眨眼帧2") if len(args.blink_frames) > 1 else bank0
        if not (2 <= len(bank0) <= 60): sys.exit(f"错误：眨眼帧数量 {len(bank0)} 超出范围（2~60）")
        for f in bank0 + bank1:
            if f.size != idle.size: sys.exit("错误：眨眼帧与 idle 尺寸不一致")
    elif args.closed:
        closed = load(args.closed)
        if closed.size != idle.size: sys.exit("错误：closed 与 idle 尺寸不一致")
        bank0 = [crossfade(looks[0], closed, w_) for w_ in blink_w]
        bank1 = [crossfade(looks[-1], closed, w_) for w_ in blink_w]
    else:
        bank0 = [looks[0].copy() for _ in blink_w]
        bank1 = [looks[-1].copy() for _ in blink_w]
    blink_n = len(bank0)

    # --- 大笑帧 ---
    if args.laugh_frames:
        laugh = dir_frames(args.laugh_frames, None, "大笑帧")
        for f in laugh:
            if f.size != idle.size: sys.exit("错误：大笑帧与 idle 尺寸不一致")
    elif args.laugh_video:
        if not shutil.which("ffmpeg"): sys.exit("错误：未找到 ffmpeg，无法抽帧")
        tmp = tempfile.mkdtemp(prefix="petlaugh_")
        print("ffmpeg 抽帧中…")
        subprocess.run(["ffmpeg", "-y", "-i", args.laugh_video, "-vf", f"fps={args.fps}",
                        os.path.join(tmp, "%04d.png")], check=True, capture_output=True)
        laugh = [load(os.path.join(tmp, f)) for f in sorted(os.listdir(tmp)) if f.endswith(".png")]
        laugh = [f.resize((w, h), Image.LANCZOS) for f in laugh]
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        base = load(args.laugh_base) if args.laugh_base else idle
        if base.size != idle.size: sys.exit("错误：laugh-base 与 idle 尺寸不一致")
        n = 24
        laugh = []
        for i in range(n):
            t = i / (n - 1)
            s = 0.07 * math.sin(2 * math.pi * 1.5 * t) * math.exp(-2.5 * t)
            laugh.append(squash_frame(base, s))

    if not (1 <= len(laugh) <= 2000): sys.exit(f"错误：大笑帧数量 {len(laugh)} 超出范围（1~2000）")
    if not (1 <= args.fps <= 120): sys.exit("错误：fps 超出范围（1~120）")

    # --- 身体区域（缺省按奶蛙比例估算）---
    poke = args.poke or (w * .5, h * .573, w * .24, h * .185)
    warp = args.warp or (h * .285, h * .815, w * .333, h * .196)
    icon = args.icon or (w * .208, h * .109, w * .608, h * .611)

    meta = {
        "width": w, "height": h, "fps": args.fps, "frames": len(laugh),
        "eyeFrames": len(looks), "blinkFrames": blink_n, "blinkFps": 30,
        "name": args.name, "id": args.id,
        "poke": {"x": poke[0], "y": poke[1], "rx": poke[2], "ry": poke[3]},
        "warp": {"top": warp[0], "bottom": warp[1], "rx": warp[2], "ry": warp[3]},
        "icon": {"x": icon[0], "y": icon[1], "w": icon[2], "h": icon[3]},
    }

    out = os.path.abspath(args.out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
        add_png(z, "idle.png", idle)
        add_png(z, "hover.png", looks[-1])
        if args.closed: add_png(z, "closed.png", load(args.closed))
        for i, im in enumerate(looks): add_png(z, f"look/{i:02d}.png", im)
        for i, im in enumerate(bank0): add_png(z, f"blink/0/{i:02d}.png", im)
        for i, im in enumerate(bank1): add_png(z, f"blink/1/{i:02d}.png", im)
        for i, im in enumerate(laugh): add_png(z, f"laugh/{i:04d}.png", im)
        z.writestr("metadata.json", json.dumps(meta, ensure_ascii=False, indent=1))

    if args.sound:
        shutil.copy(args.sound, os.path.join(os.path.dirname(out), "原版笑声.wav"))

    print(f"完成：{out}")
    print(f"  画面 {w}x{h}｜转眼 {len(looks)} 帧｜眨眼 {blink_n} 帧｜大笑 {len(laugh)} 帧 @ {args.fps}fps")
    missing = []
    if not args.look_frames and not args.hover: missing.append("眼睛不跟鼠标（补 --hover 或 --look-frames）")
    if not args.blink_frames and not args.closed: missing.append("不眨眼（补 --closed 或 --blink-frames）")
    if not (args.laugh_frames or args.laugh_video): missing.append("大笑是程序化弹跳（想要原味大笑就补 --laugh-frames / --laugh-video）")
    if not args.sound: missing.append("没有笑声（补 --sound）")
    for m in missing: print("  · " + m)
    print("把 素材.nwp 放到 exe 旁边，双击 exe 即可。戳肚子位置不对就加 --poke 参数重打包。")


if __name__ == "__main__":
    main()
