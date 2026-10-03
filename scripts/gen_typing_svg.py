#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 profile 打字机动画 SVG —— 文泉驿点阵正黑 / 随机顺序 / 逐字节奏。

行为:
  - 每个词打字快 (CHAR_DELAY)
  - 词之间间隔大 (SPACE_DELAY)
  - 标点(，。；！？等)后额外停顿 (PUNCT_DELAY)
  - 整句打完长停顿 (HOLD) 再切下一条
  - 每条顺序随机; 配合 GitHub Action 定时重跑即可"随机展示"
"""
import os, glob, random, sys
from PIL import Image, ImageDraw, ImageFont

SIZE, IDX, SCALE, PAD = 16, 2, 2, 2
CHAR_DELAY, SPACE_DELAY, PUNCT_DELAY, HOLD, TAIL = 0.045, 0.40, 0.45, 2.20, 0.40
PUNCT = set("，。；：！？、,.;:!?…—")

ITEMS = ["原神", "明日方舟", "明日方舟：终末地", "Minecraft", "Github", "VS Code",
         "DeepSeek Harness", "ESP32 S3", "ESP8266", "Arduino IDE", "Arduino UNO"]
LINES = [x + "，启动！" for x in ITEMS]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "typing.svg")


def find_font():
    cands = ["/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"]
    cands += glob.glob("/usr/share/fonts/**/wqy-zenhei.ttc", recursive=True)
    cands += glob.glob(os.path.join(ROOT, "assets", "*.ttc"))
    for p in cands:
        if os.path.exists(p):
            return p
    sys.exit("未找到文泉驿正黑字体, 请安装 fonts-wqy-zenhei")


FONT_PATH = find_font()


def bitmap(txt, font):
    b = font.getbbox(txt)
    w, h = b[2] - b[0], b[3] - b[1]
    img = Image.new("L", (w, h), 255)
    ImageDraw.Draw(img).text((-b[0], -b[1]), txt, font=font, fill=0)
    px = img.load()
    runs = []
    for y in range(h):
        x = 0
        while x < w:
            if px[x, y] < 128:
                x0 = x
                while x < w and px[x, y] < 128:
                    x += 1
                runs.append((x0, y, x - x0))
            else:
                x += 1
    return w, h, runs


def main():
    font = ImageFont.truetype(FONT_PATH, SIZE, index=IDX)
    order = LINES[:]
    random.shuffle(order)

    metas, maxW = [], 0
    for t in order:
        w, h, runs = bitmap(t, font)
        width_at, times, acc = [], [], 0.0
        for i, ch in enumerate(t, 1):
            acc += CHAR_DELAY
            if ch in PUNCT:
                acc += PUNCT_DELAY
            elif ch == " ":
                acc += SPACE_DELAY
            pb = font.getbbox(t[:i])
            width_at.append(pb[2] - pb[0])
            times.append(acc)
        if width_at:
            width_at[-1] = w
        metas.append(dict(t=t, w=w, h=h, runs=runs,
                          width_at=width_at, times=times, type=acc))
        maxW = max(maxW, w)

    H = max(m["h"] for m in metas)
    VW, VH = maxW + PAD * 2, H + PAD * 2

    t0 = 0.0
    for m in metas:
        m["t0"] = t0
        t0 += m["type"] + HOLD
    CYCLE = round(t0 + TAIL, 4)

    def keys(m):
        ks, vs, last = [0.0], [0.0], 0.0
        ks.append(m["t0"] / CYCLE); vs.append(0.0)
        for wd, tt in zip(m["width_at"], m["times"]):
            k = (m["t0"] + tt) / CYCLE
            if k <= last + 1e-6:
                k = last + 1e-5
            ks.append(k); vs.append(wd); last = k
        ae = max(last + 1e-5, (m["t0"] + m["type"]) / CYCLE)
        ks.append(ae); vs.append(m["w"]); last = ae
        c = max(last + 1e-5, (m["t0"] + m["type"] + HOLD) / CYCLE)
        ks.append(c); vs.append(m["w"]); last = c
        k2 = min(1.0, last + 1e-3)
        ks.append(k2); vs.append(0.0)
        if ks[-1] < 1.0:
            ks.append(1.0); vs.append(0.0)
        return ks, vs

    fmt = lambda arr: ";".join(f"{v:g}" for v in arr)

    P = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{VW*SCALE}" height="{VH*SCALE}" '
         f'viewBox="0 0 {VW} {VH}" shape-rendering="crispEdges">', "<defs>"]
    for i, m in enumerate(metas):
        ks, vs = keys(m)
        P.append(f'<clipPath id="cp{i}"><rect x="0" y="0" height="{VH}" width="0">'
                 f'<animate attributeName="width" values="{fmt(vs)}" keyTimes="{fmt(ks)}" '
                 f'dur="{CYCLE}s" repeatCount="indefinite"/></rect></clipPath>')
    P.append("</defs>")
    P.append(f'<rect width="{VW}" height="{VH}" fill="#0d1117"/>')
    P.append('<g fill="#22d3ee">')
    for i, m in enumerate(metas):
        P.append(f'<g clip-path="url(#cp{i})">' + "".join(
            f'<rect x="{x+PAD}" y="{y+PAD}" width="{rw}" height="1"/>'
            for (x, y, rw) in m["runs"]) + "</g>")
    P.append("</g>")
    for i, m in enumerate(metas):
        ks, vs = keys(m)
        xs = [PAD + v for v in vs]
        a = m["t0"] / CYCLE
        c = min(1.0, (m["t0"] + m["type"] + HOLD) / CYCLE)
        k2 = min(1.0, c + 1e-3)
        ok = f"0;{a:g};{a:g};{c:g};{k2:g};1"
        ov = "0;0;1;1;0;0"
        P.append(f'<rect y="{PAD}" width="{max(1.0, SCALE*0.75)}" height="{m["h"]}" fill="#e2e8f0" opacity="0">'
                 f'<animate attributeName="x" values="{fmt(xs)}" keyTimes="{fmt(ks)}" dur="{CYCLE}s" repeatCount="indefinite"/>'
                 f'<animate attributeName="opacity" values="{ov}" keyTimes="{ok}" dur="{CYCLE}s" repeatCount="indefinite"/>'
                 f'</rect>')
    P.append("</svg>")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("".join(P))
    import xml.dom.minidom
    xml.dom.minidom.parseString("".join(P))
    print(f"ok | viewBox {VW}x{VH} | 显示 {VW*SCALE}x{VH*SCALE} | "
          f"{os.path.getsize(OUT)//1024}KB | 周期 {CYCLE}s | 顺序 {order}")


if __name__ == "__main__":
    main()
