#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 profile 打字机动画 SVG —— 文泉驿点阵正黑 / 整字蹦出 / 随机顺序。

要点:
  - 每个字 = 一个独立 <g>, 用 discrete opacity 控制显隐
    => 字一定是"整字完整出现", 不可能出现半个字
  - 每个字旁边带一个光标, 随字前进
  - 逐字速度快 (CHAR_DELAY) / 词间隔大 (SPACE_DELAY)
  - 标点(，。；！？等)后额外停顿 (PUNCT_DELAY)
  - 整句打完长停顿 (HOLD) 再随机切下一条
"""
import os, glob, random, sys
from PIL import Image, ImageDraw, ImageFont

SIZE, IDX, SCALE, PAD = 16, 2, 2, 2
CHAR_DELAY, PUNCT_DELAY, HOLD, TAIL = 0.08, 0.45, 2.20, 0.40
SPACE_DELAY = CHAR_DELAY * 0.5   # 空格额外停顿 -> 词间隔 = 1.5 字
PUNCT = set("，。；：！？、,.;:!?…—")
FG, CURSOR, BG = "#22d3ee", "#e2e8f0", "#0d1117"
CURSOR_W = 8   # 光标整块宽度

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


def runs_of(img):
    """把二值图的亮像素按水平游程合并成 rect 列表。"""
    w, h = img.size
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
    return runs


def char_cells(t, font):
    """返回每字: (runs, adv_before, adv_after) —— 每字独立完整渲染。"""
    total_adv = int(font.getlength(t))
    W = PAD * 2 + total_adv + 8
    cells = []
    for i, ch in enumerate(t):
        adv_b = font.getlength(t[:i])
        adv_a = font.getlength(t[:i + 1])
        img = Image.new("L", (W, SIZE + PAD * 2), 255)
        ImageDraw.Draw(img).text((PAD + adv_b, PAD), ch, font=font, fill=0)
        cells.append((runs_of(img), adv_b, adv_a))
    return cells, W


def main():
    font = ImageFont.truetype(FONT_PATH, SIZE, index=IDX)
    order = LINES[:]
    random.shuffle(order)

    metas, maxW = [], 0
    for t in order:
        cells, W = char_cells(t, font)
        # 每字出现时刻
        acc, times = 0.0, []
        for ch in t:
            acc += CHAR_DELAY
            if ch in PUNCT:
                acc += PUNCT_DELAY
            elif ch == " ":
                acc += SPACE_DELAY
            times.append(acc)
        metas.append(dict(t=t, cells=cells, times=times, type=acc))
        maxW = max(maxW, W)

    VH = SIZE + PAD * 2
    for m in metas:                       # 统一画布宽
        m["W"] = maxW

    t0 = 0.0
    for m in metas:
        m["t0"] = t0
        t0 += m["type"] + HOLD
    CYCLE = round(t0 + TAIL, 4)

    P = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{maxW*SCALE}" height="{VH*SCALE}" '
         f'viewBox="0 0 {maxW} {VH}" shape-rendering="crispEdges">',
         f'<rect width="{maxW}" height="{VH}" fill="{BG}"/>']

    for m in metas:
        t_end = m["t0"] + m["type"] + HOLD
        for ci, (runs, adv_b, adv_a) in enumerate(m["cells"]):
            a = max(1e-4, (m["t0"] + m["times"][ci]) / CYCLE)
            c = min(0.9999, t_end / CYCLE)
            if c <= a:
                c = min(0.9999, a + 1e-3)
            c2 = min(0.99995, c + 1e-4)
            kt = f"0;{a:g};{c:g};{c2:g};1"
            P.append(f'<g opacity="0">'
                     f'<animate attributeName="opacity" values="0;1;1;0;0" '
                     f'keyTimes="{kt}" calcMode="discrete" dur="{CYCLE}s" repeatCount="indefinite"/>'
                     + "".join(f'<rect x="{x}" y="{y}" width="{rw}" height="1" fill="{FG}"/>'
                               for (x, y, rw) in runs)
                     + '</g>')
    # ---- 每行一个"整块"光标 (discrete 跳格, 行结束即消失) ----
    for m in metas:
        t_end = m["t0"] + m["type"] + HOLD
        a0 = max(1e-4, m["t0"] / CYCLE)
        ce = min(0.9999, t_end / CYCLE)
        ce2 = min(0.99995, ce + 1e-4)
        # x: 逐字跳格
        kx, vx = [0.0], [PAD]
        last = 0.0
        for ci, (runs, adv_b, adv_a) in enumerate(m["cells"]):
            k = max(last + 1e-6, (m["t0"] + m["times"][ci]) / CYCLE)
            kx.append(k); vx.append(PAD + adv_a); last = k
        kx.append(max(last + 1e-6, ce)); vx.append(vx[-1])
        if kx[-1] < 1.0:
            kx.append(1.0); vx.append(vx[-1])
        fx = lambda arr: ";".join(f"{v:g}" for v in arr)
        P.append(f'<rect y="{PAD}" width="{CURSOR_W}" height="{SIZE}" fill="{CURSOR}" opacity="0">'
                 f'<animate attributeName="x" values="{fx(vx)}" keyTimes="{fx(kx)}" calcMode="discrete" dur="{CYCLE}s" repeatCount="indefinite"/>'
                 f'<animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;{a0:g};{ce:g};{ce2:g};1" calcMode="discrete" dur="{CYCLE}s" repeatCount="indefinite"/>'
                 f'</rect>')

    P.append("</svg>")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    svg = "".join(P)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(svg)
    import xml.dom.minidom
    xml.dom.minidom.parseString(svg)
    print(f"ok | {maxW*SCALE}x{VH*SCALE} | {os.path.getsize(OUT)//1024}KB | "
          f"周期 {CYCLE}s | 每字 {CHAR_DELAY}s | 顺序 {order}")


if __name__ == "__main__":
    main()
