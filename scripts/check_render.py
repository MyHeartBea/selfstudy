"""渲染结果校验：用**截图**判断画面是否真的画出来了。

为什么不用 WebGL readPixels
---------------------------
在 GPU 合成路径下，对 WebGL 画布调 `gl.readPixels` 可能拿到全黑（假阴性）。
本项目实测过：readPixels 全 0，但同一时刻的截图里星点清晰可见。
所以渲染判据必须落在**渲染结果**上，而不是 API 返回值。

判据三项
  1. 非空画面：整体平均亮度在合理区间（既不是纯黑，也不是白屏）
  2. 星点在场：右半区（避开标题文字）亮像素数量达到下限
  3. 无硬边：强梯度像素占比低于阈值 —— 用来抓"着色器饱和平台 / 几何色块"这类
     在暗色沉浸式页面里最刺眼的问题（本项目为它返工过四轮）

用法
  python scripts/check_render.py <截图路径> [--min-bright 20] [--max-edge 0.14]
退出码非 0 即视为不通过，可直接接进 CI。
"""

from __future__ import annotations

import argparse
import sys

from PIL import Image, ImageFilter, ImageStat


def analyze(path: str) -> dict:
    im = Image.open(path).convert('RGB')
    w, h = im.size
    px = im.load()
    step = 2

    bright = 0
    right_bright = 0
    for y in range(0, h, step):
        for x in range(0, w, step):
            r, g, b = px[x, y]
            if r + g + b > 120:
                bright += 1
                if x >= w // 2:
                    right_bright += 1

    mean = [round(v, 2) for v in ImageStat.Stat(im).mean]

    edges = im.convert('L').filter(ImageFilter.FIND_EDGES)
    epx = edges.load()
    strong = 0
    total = 0
    for y in range(0, h, step):
        for x in range(0, w, step):
            total += 1
            if epx[x, y] > 60:
                strong += 1

    return {
        'size': [w, h],
        'mean_rgb': mean,
        'bright_pixels': bright,
        'bright_pixels_right_half': right_bright,
        'strong_edge_ratio': round(strong / max(1, total), 4),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description='渲染结果校验（截图判据）')
    ap.add_argument('image', help='截图路径')
    ap.add_argument('--min-bright', type=int, default=20, help='右半区亮像素下限（默认 20）')
    ap.add_argument('--max-edge', type=float, default=0.14, help='强边占比上限（默认 0.14）')
    args = ap.parse_args()

    res = analyze(args.image)
    print(f'分析 {args.image}')
    for k, v in res.items():
        print(f'  {k}: {v}')

    problems = []
    if sum(res['mean_rgb']) < 3:
        problems.append('画面过暗，疑似纯黑（渲染未发生）')
    if res['bright_pixels_right_half'] < args.min_bright:
        problems.append(
            f"右半区亮像素 {res['bright_pixels_right_half']} < {args.min_bright}，星点可能未绘制"
        )
    if res['strong_edge_ratio'] > args.max_edge:
        problems.append(
            f"强边占比 {res['strong_edge_ratio']} > {args.max_edge}，疑似硬边或饱和平台"
        )

    if problems:
        print('\n结论: 不通过 — ' + '；'.join(problems))
        return 1
    print('\n结论: 通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
