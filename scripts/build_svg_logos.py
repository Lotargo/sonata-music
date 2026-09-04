import os
import math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle, PathPatch
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties
from matplotlib.path import Path

RAY_SPECS = [
    (8,   0.65, 3.8,  1.5),
    (22,  0.80, 4.2,  3.0),
    (36,  1.00, 4.8,  4.5), # MAX FLARE 1
    (48,  0.75, 3.6,  3.5),
    (60,  0.96, 4.6,  4.0), # MAX FLARE 2
    (74,  0.82, 4.0,  3.0),
    (88,  0.64, 3.4,  2.0),
    (104, 0.70, 3.8,  1.0),
    (118, 0.58, 3.2, -0.5),
    (132, 0.72, 4.0, -1.5),
    (146, 0.54, 3.0, -1.5),
    (160, 0.62, 3.6, -1.0),
    (174, 0.48, 2.8,  0.0),
    (190, 0.53, 3.0,  0.5),
    (206, 0.44, 2.6,  1.0),
    (222, 0.51, 3.0,  1.5),
    (238, 0.46, 2.8,  1.5),
    (254, 0.57, 3.4,  2.0),
    (270, 0.50, 2.8,  1.5),
    (286, 0.64, 3.8,  2.5),
    (302, 0.55, 3.2,  2.0),
    (318, 0.70, 4.0,  3.0),
    (334, 0.59, 3.4,  2.5),
    (350, 0.62, 3.6,  2.0),
]

def get_rays_path(cx, cy, max_r=55.0, r_black=17.5):
    r_inner = r_black * 0.75
    paths = []
    for ang, factor, hw, lean in RAY_SPECS:
        length = max_r * factor
        rad_b1 = math.radians(ang - hw)
        rad_b2 = math.radians(ang + hw)
        rad_tip = math.radians(ang + lean)
        bx1 = cx + r_inner * math.cos(rad_b1)
        by1 = cy - r_inner * math.sin(rad_b1)
        bx2 = cx + r_inner * math.cos(rad_b2)
        by2 = cy - r_inner * math.sin(rad_b2)
        tx = cx + length * math.cos(rad_tip)
        ty = cy - length * math.sin(rad_tip)
        paths.append(f'M {bx1:.2f} {by1:.2f} L {tx:.2f} {ty:.2f} L {bx2:.2f} {by2:.2f} Z')
    return ' '.join(paths)

def text_to_svg_path(text, font_path, size, offset_x, baseline_y):
    fp = FontProperties(fname=font_path, size=size)
    tp = TextPath((offset_x, 0), text, prop=fp)
    cmd = []
    i = 0
    sv = tp.vertices
    sc = tp.codes
    while i < len(sv):
        code = sc[i]
        x, y = sv[i]
        y_svg = baseline_y - y
        if code == 1:
            cmd.append(f'M {x:.2f} {y_svg:.2f}')
            i += 1
        elif code == 2:
            cmd.append(f'L {x:.2f} {y_svg:.2f}')
            i += 1
        elif code == 3:
            cx, cy = x, y_svg
            x2, y2 = sv[i+1][0], baseline_y - sv[i+1][1]
            cmd.append(f'Q {cx:.2f} {cy:.2f} {x2:.2f} {y2:.2f}')
            i += 2
        elif code == 4:
            c1x, c1y = x, y_svg
            c2x, c2y = sv[i+1][0], baseline_y - sv[i+1][1]
            x3, y3 = sv[i+2][0], baseline_y - sv[i+2][1]
            cmd.append(f'C {c1x:.2f} {c1y:.2f} {c2x:.2f} {c2y:.2f} {x3:.2f} {y3:.2f}')
            i += 3
        elif code == 79:
            cmd.append('Z')
            i += 1
        else:
            i += 1
    return ' '.join(cmd), tp

os.makedirs('music/static/music/img', exist_ok=True)
font_bold = 'scripts/fonts/Montserrat-Bold-Static.ttf'

# ==============================================================================
# 1. logo-icon.svg & favicon.svg (48x48 standalone Black Sun)
# ==============================================================================
cx_i, cy_i = 24.0, 24.0
r_black_i = 7.6
max_r_i = 23.5
rays_i = get_rays_path(cx_i, cy_i, max_r=max_r_i, r_black=r_black_i)

svg_icon = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">
  <defs>
    <linearGradient id="sunRaysGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FFE54C" />
      <stop offset="40%" stop-color="#FFD21E" />
      <stop offset="100%" stop-color="#FFAC00" />
    </linearGradient>
  </defs>
  <!-- Asymmetric Solar Rays Burst -->
  <path d="{rays_i}" fill="url(#sunRaysGrad)" />
  <!-- Solid Black Sun Core with Crisp Eclipse Edge (No inner dots/dashes) -->
  <circle cx="{cx_i:.1f}" cy="{cy_i:.1f}" r="{r_black_i:.1f}" fill="#060606" stroke="#FFD21E" stroke-width="1.6" />
</svg>'''

with open('music/static/music/img/logo-icon.svg', 'w', encoding='utf-8') as f:
    f.write(svg_icon)

with open('music/static/music/img/favicon.svg', 'w', encoding='utf-8') as f:
    f.write(svg_icon)

# ==============================================================================
# 2. favicon.png (transparent high-res PNG)
# ==============================================================================
fig, ax = plt.subplots(figsize=(2, 2), dpi=96)
fig.patch.set_alpha(0.0)
ax.set_facecolor('none')
ax.set_xlim(0, 48)
ax.set_ylim(48, 0)
ax.axis('off')

r_inner_i = r_black_i * 0.75
for ang, factor, hw, lean in RAY_SPECS:
    length = max_r_i * factor
    rad_b1 = math.radians(ang - hw)
    rad_b2 = math.radians(ang + hw)
    rad_tip = math.radians(ang + lean)
    bx1 = cx_i + r_inner_i * math.cos(rad_b1)
    by1 = cy_i - r_inner_i * math.sin(rad_b1)
    bx2 = cx_i + r_inner_i * math.cos(rad_b2)
    by2 = cy_i - r_inner_i * math.sin(rad_b2)
    tx = cx_i + length * math.cos(rad_tip)
    ty = cy_i - length * math.sin(rad_tip)
    poly = Polygon([[bx1, by1], [tx, ty], [bx2, by2]], closed=True, facecolor='#FFD21E', edgecolor='none')
    ax.add_patch(poly)

ax.add_patch(Circle((cx_i, cy_i), r_black_i, facecolor='#060606', edgecolor='#FFD21E', linewidth=1.6))
plt.savefig('music/static/music/img/favicon.png', transparent=True, bbox_inches='tight', pad_inches=0.02)
plt.close(fig)

# ==============================================================================
# 3. logo-full.svg (ViewBox 0 0 180 96: 2x Larger Sun, Tight Text Spacing)
# ==============================================================================
cx_f, cy_f = 48.0, 48.0
r_black_f = 17.5 # 2x scale
max_r_f = 55.0   # 2x scale
rays_f = get_rays_path(cx_f, cy_f, max_r=max_r_f, r_black=r_black_f)

# Tight text placement pulling text closer to the sun
text_x = 84.0
sz_s = 20.5
sz_m = 18.0
gap_y = 2.5

# Calculate accurate vertical centering
fp_s = FontProperties(fname=font_bold, size=sz_s)
tp_s_tmp = TextPath((text_x, 0), 'SONATA', prop=fp_s)
bb_s = tp_s_tmp.get_extents()

fp_m = FontProperties(fname=font_bold, size=sz_m)
tp_m_tmp = TextPath((text_x, 0), 'music', prop=fp_m)
bb_m = tp_m_tmp.get_extents()

total_h = bb_s.height + gap_y + bb_m.height
top_y = cy_f - total_h / 2.0
baseline_s = top_y + bb_s.height
baseline_m = baseline_s + gap_y + bb_m.height - 2.0

sonata_d, tp_s = text_to_svg_path('SONATA', font_bold, size=sz_s, offset_x=text_x, baseline_y=baseline_s)
music_d, tp_m = text_to_svg_path('music', font_bold, size=sz_m, offset_x=text_x, baseline_y=baseline_m)

view_w = 180
view_h = 96

svg_full = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {view_w} {view_h}" width="{view_w}" height="{view_h}">
  <defs>
    <linearGradient id="sunRaysFull" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FFE54C" />
      <stop offset="40%" stop-color="#FFD21E" />
      <stop offset="100%" stop-color="#FFAC00" />
    </linearGradient>
  </defs>
  <!-- Mark: Asymmetric Black Sun (2x Scale, Dominant Hero) -->
  <g id="brand-sun">
    <path d="{rays_f}" fill="url(#sunRaysFull)" />
    <!-- Solid Black Sun Core with Crisp Eclipse Edge (No inner dots/dashes) -->
    <circle cx="{cx_f:.1f}" cy="{cy_f:.1f}" r="{r_black_f:.1f}" fill="#060606" stroke="#FFD21E" stroke-width="2.6" />
  </g>
  <!-- Typography: SONATA (uppercase, white) + music (lowercase, yellow) in Montserrat Bold -->
  <g id="brand-typography">
    <path d="{sonata_d}" fill="#FFFFFF" fill-rule="evenodd" />
    <path d="{music_d}" fill="#FFD21E" fill-rule="evenodd" />
  </g>
</svg>'''

with open('music/static/music/img/logo-full.svg', 'w', encoding='utf-8') as f:
    f.write(svg_full)

# ==============================================================================
# 4. logo-full.png (High-Res Transparent Raster Master: 720x384)
# ==============================================================================
fig, ax = plt.subplots(figsize=(7.5, 4.0), dpi=96)
fig.patch.set_alpha(0.0)
ax.set_facecolor('none')
ax.set_xlim(-2, view_w + 2)
ax.set_ylim(view_h + 2, -2)
ax.axis('off')
ax.set_aspect('equal')

# Solar rays
r_inner_f = r_black_f * 0.75
for ang, factor, hw, lean in RAY_SPECS:
    length = max_r_f * factor
    rad_b1 = math.radians(ang - hw)
    rad_b2 = math.radians(ang + hw)
    rad_tip = math.radians(ang + lean)
    bx1 = cx_f + r_inner_f * math.cos(rad_b1)
    by1 = cy_f - r_inner_f * math.sin(rad_b1)
    bx2 = cx_f + r_inner_f * math.cos(rad_b2)
    by2 = cy_f - r_inner_f * math.sin(rad_b2)
    tx = cx_f + length * math.cos(rad_tip)
    ty = cy_f - length * math.sin(rad_tip)
    poly = Polygon([[bx1, by1], [tx, ty], [bx2, by2]], closed=True, facecolor='#FFD21E', edgecolor='none')
    ax.add_patch(poly)

# Black Sun Core
ax.add_patch(Circle((cx_f, cy_f), r_black_f, facecolor='#060606', edgecolor='#FFD21E', linewidth=2.6))

# SONATA
verts_s = [[v[0], baseline_s - v[1]] for v in tp_s.vertices]
ax.add_patch(PathPatch(Path(verts_s, tp_s.codes), facecolor='#FFFFFF', edgecolor='none'))

# music
verts_m = [[v[0], baseline_m - v[1]] for v in tp_m.vertices]
ax.add_patch(PathPatch(Path(verts_m, tp_m.codes), facecolor='#FFD21E', edgecolor='none'))

plt.savefig('music/static/music/img/logo-full.png', transparent=True, bbox_inches='tight', pad_inches=0.04)
plt.close(fig)

# ==============================================================================
# 5. Visual Preview Artifact on Checkerboard Background
# ==============================================================================
fig, ax = plt.subplots(figsize=(10, 5), dpi=140)
fig.patch.set_facecolor('#040e11')

# Draw checkerboard matching user view
for i in range(-2, view_w + 14, 10):
    for j in range(-2, view_h + 10, 10):
        if (i // 10 + j // 10) % 2 == 0:
            ax.add_patch(plt.Rectangle((i, j), 10, 10, color='#14252a'))
        else:
            ax.add_patch(plt.Rectangle((i, j), 10, 10, color='#0b181c'))

# Solar rays
for ang, factor, hw, lean in RAY_SPECS:
    length = max_r_f * factor
    rad_b1 = math.radians(ang - hw)
    rad_b2 = math.radians(ang + hw)
    rad_tip = math.radians(ang + lean)
    bx1 = cx_f + r_inner_f * math.cos(rad_b1)
    by1 = cy_f - r_inner_f * math.sin(rad_b1)
    bx2 = cx_f + r_inner_f * math.cos(rad_b2)
    by2 = cy_f - r_inner_f * math.sin(rad_b2)
    tx = cx_f + length * math.cos(rad_tip)
    ty = cy_f - length * math.sin(rad_tip)
    ax.add_patch(Polygon([[bx1, by1], [tx, ty], [bx2, by2]], closed=True, facecolor='#FFD21E', edgecolor='none'))

ax.add_patch(Circle((cx_f, cy_f), r_black_f, facecolor='#060606', edgecolor='#FFD21E', linewidth=2.6))
ax.add_patch(PathPatch(Path(verts_s, tp_s.codes), facecolor='#FFFFFF', edgecolor='none'))
ax.add_patch(PathPatch(Path(verts_m, tp_m.codes), facecolor='#FFD21E', edgecolor='none'))

ax.set_xlim(-2, view_w + 2)
ax.set_ylim(view_h + 2, -2)
ax.axis('off')
ax.set_aspect('equal')
ax.set_title('Sonata Music (2x Sun Scale, Snug Text Spacing, No Dead Air)', color='#FFD21E', fontsize=12, pad=10)

plt.tight_layout()
out_preview = 'C:/Users/etotm/.gemini/antigravity-ide/brain/91d3e00c-d89d-4bf6-9fd2-5ce77924f514/logo_final_preview.png'
plt.savefig(out_preview, facecolor='#040e11', edgecolor='none')
plt.close(fig)

print('Updated 2x scale logos generated successfully!')
