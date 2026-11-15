"""Generate a CC0 pine-bough alpha sprite for the foliage cards."""
import math
import random
from PIL import Image, ImageDraw, ImageFilter

W = 2048
S = 4  # supersample factor relative to the 512-ish target? we draw at 2048 and use 1024
rnd = random.Random(20261115)
img = Image.new('RGBA', (W, W), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

GREENS = [(44, 62, 30), (57, 79, 38), (71, 95, 46), (87, 111, 56),
          (36, 52, 26)]
BROWNS = [(74, 55, 35), (95, 72, 45), (60, 44, 28)]


def needle(x, y, ang, ln, w, col, alpha=235):
    x2 = x + math.cos(ang) * ln
    y2 = y + math.sin(ang) * ln
    d.line((x, y, x2, y2), fill=(*col, alpha), width=max(1, int(w)))
    # tiny lighter tip
    if rnd.random() < 0.35:
        d.line((x2 - math.cos(ang) * ln * 0.18, y2 - math.sin(ang) * ln * 0.18,
                x2, y2), fill=(min(255, col[0] + 14), min(255, col[1] + 24),
                               min(255, col[2] + 8), alpha), width=max(1, int(w * 0.7)))


def bough(x0, y0, x1, y1, width, depth=0):
    # slightly wavy brown stem
    n = 8
    pts = []
    for i in range(n + 1):
        t = i / n
        px = x0 + (x1 - x0) * t + math.sin(t * 7 + x0 * 0.01) * 10
        py = y0 + (y1 - y0) * t + math.sin(t * 9 + y0 * 0.01) * 8
        pts.append((px, py))
    for i in range(n):
        d.line((pts[i], pts[i + 1]), fill=(*BROWNS[0], 255), width=width)
        d.line((pts[i], pts[i + 1]), fill=(*BROWNS[2], 150),
               width=max(1, width - 3))
    # needle clusters along the bough
    steps = int(math.hypot(x1 - x0, y1 - y0) / 14)
    base_ang = math.atan2(y1 - y0, x1 - x0)
    for i in range(steps):
        t = (i + 1) / (steps + 1)
        px = x0 + (x1 - x0) * t + math.sin(t * 7 + x0 * 0.01) * 10
        py = y0 + (y1 - y0) * t + math.sin(t * 9 + y0 * 0.01) * 8
        # node twig
        if rnd.random() < 0.5:
            d.line((px, py, px + math.cos(base_ang) * 18,
                    py + math.sin(base_ang) * 18),
                   fill=(*BROWNS[1], 180), width=3)
        ncount = rnd.randint(11, 18)
        for k in range(ncount):
            side = -1 if k % 2 else 1
            spread = rnd.uniform(0.45, 1.25)
            ang = base_ang + side * spread + rnd.uniform(-0.25, 0.25)
            ln = rnd.uniform(70, 190) * (0.75 + 0.45 * (1 - abs(t - 0.5) * 2))
            col = rnd.choice(GREENS)
            needle(px + rnd.uniform(-8, 8), py + rnd.uniform(-5, 5),
                   ang, ln, rnd.uniform(2.2, 4.0), col)
    return pts


# three stacked boughs fill the card with a dense needle mass
bough(70, 760, 1980, 780, 9)
bough(50, 1015, 1990, 1035, 11)
bough(80, 1270, 1960, 1250, 9)
# secondary boughs
for (sx, sy, ex, ey, w) in [
        (520, 1000, 850, 650, 6), (1180, 1020, 1500, 1400, 6),
        (1450, 1030, 1780, 760, 5), (820, 990, 610, 1360, 5),
        (300, 1015, 160, 740, 4), (620, 760, 720, 520, 4),
        (1500, 1250, 1580, 1500, 4)]:
    bough(sx, sy, ex, ey, w)

# extra free needle sprays at the margins
for i in range(160):
    ang = rnd.uniform(0, math.tau)
    x = rnd.uniform(60, W - 60)
    y = 1024 + rnd.uniform(-330, 330)
    needle(x, y, ang, rnd.uniform(25, 70), rnd.uniform(1.4, 2.4),
           rnd.choice(GREENS), alpha=rnd.randint(100, 180))

img = img.resize((1024, 1024), Image.LANCZOS)
# soften the alpha edge slightly
r, g, b, a = img.split()
a = a.filter(ImageFilter.GaussianBlur(0.4))
img = Image.merge('RGBA', (r, g, b, a))
img.save('scripts/textures/pine_bough.png')
print('saved scripts/textures/pine_bough.png')
