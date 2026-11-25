"""
Generate a true 16-bit RGB PNG test chart encoded in DaVinci Wide Gamut / DaVinci Intermediate (DWG/DI)
for side-by-side comparison of shadow desaturation tools in DaVinci Resolve (followed by a DWG/DI -> Rec.709 CST).
"""

import os
import struct
import zlib
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(__file__).resolve().parent.parent

# Official DaVinci Intermediate constants (matching DWG_Shadow_Desat.dctl)
DI_A = 0.0075
DI_B = 7.0
DI_C = 0.07329248
DI_M = 10.44426855
DI_LIN_CUT = 0.00262409
DI_LOG_CUT = 0.02740668

# Exact Rec.709 Linear <-> DaVinci Wide Gamut Linear matrices
M_709_TO_DWG = np.array(
    [
        [0.562767, 0.323517, 0.113716],
        [0.077755, 0.749577, 0.172668],
        [0.064669, 0.191999, 0.743332],
    ],
    dtype=np.float64,
)
M_DWG_TO_709 = np.linalg.inv(M_709_TO_DWG)

W, H = 1920, 1080


def di_to_linear(y: np.ndarray) -> np.ndarray:
    y = np.asarray(y, dtype=np.float64)
    return np.where(y <= DI_LOG_CUT, y / DI_M, np.exp2((y / DI_C) - DI_B) - DI_A)


def linear_to_di(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    safe_x = np.maximum(x, -DI_A + 1e-8)
    return np.where(x <= DI_LIN_CUT, x * DI_M, (np.log2(safe_x + DI_A) + DI_B) * DI_C)


def rec709_lin_to_dwg_di(rgb709_lin: np.ndarray) -> np.ndarray:
    shape = rgb709_lin.shape
    dwg_lin = rgb709_lin.reshape(-1, 3) @ M_709_TO_DWG.T
    return linear_to_di(dwg_lin).reshape(shape)


def dwg_di_to_rec709_display(di_img: np.ndarray) -> np.ndarray:
    """Simulate a standard DWG/DI -> Rec.709 Gamma 2.4 CST for visual inspection."""
    dwg_lin = di_to_linear(di_img)
    lin709 = dwg_lin.reshape(-1, 3) @ M_DWG_TO_709.T
    lin709 = np.clip(lin709, 0.0, 1.0).reshape(di_img.shape)
    return np.power(lin709, 1.0 / 2.4)


def make_equal_luma_color_709(hue_rgb709: np.ndarray, y_target: np.ndarray, sat_factor: np.ndarray = None) -> np.ndarray:
    """
    Scale a Rec.709 linear hue direction to exact luminance y_target,
    desaturating toward neutral gray only where needed to stay inside Rec.709 [0, 1].
    """
    y0 = 0.2126 * hue_rgb709[0] + 0.7152 * hue_rgb709[1] + 0.0722 * hue_rgb709[2]
    scaled = hue_rgb709 * (y_target[..., None] / y0)
    if sat_factor is not None:
        gray = y_target[..., None]
        scaled = gray + (scaled - gray) * sat_factor[..., None]

    # Softly keep within Rec.709 [0, 1] while preserving exact luminance Y
    gray = y_target[..., None]
    over = np.max(scaled, axis=-1) - 1.0
    if np.any(over > 0):
        max_c = np.max(scaled, axis=-1)
        denom = np.maximum(max_c - y_target, 1e-8)
        t_fit = np.where(max_c > 1.0, np.clip((1.0 - y_target) / denom, 0.0, 1.0), 1.0)
        scaled = gray + (scaled - gray) * t_fit[..., None]

    under = -np.min(scaled, axis=-1)
    if np.any(under > 0):
        min_c = np.min(scaled, axis=-1)
        denom = np.maximum(y_target - min_c, 1e-8)
        t_fit = np.where(min_c < 0.0, np.clip(y_target / denom, 0.0, 1.0), 1.0)
        scaled = gray + (scaled - gray) * t_fit[..., None]

    return np.clip(scaled, 0.0, 1.0)


def load_font(size: int):
    candidates = [
        # macOS (Apple Silicon / Intel)
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/SFNSMono.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        # Windows
        r"C:\Windows\Fonts\consolab.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_text_layer(canvas_di: np.ndarray, draw_fn, text_di: float = 0.42):
    """Draw crisp anti-aliased neutral-gray text/lines onto DWG/DI canvas."""
    mask_img = Image.new("L", (W, H), 0)
    draw = ImageDraw.Draw(mask_img)
    draw_fn(draw)
    alpha = np.asarray(mask_img, dtype=np.float64) / 255.0
    alpha3 = alpha[..., None]
    canvas_di[:] = canvas_di * (1.0 - alpha3) + text_di * alpha3


def write_png_16bit_rgb(path: str, rgb_u16: np.ndarray):
    """Write a standard lossless 16-bit RGB PNG (bit_depth=16, color_type=2) directly via zlib."""
    assert rgb_u16.dtype == np.uint16 and rgb_u16.ndim == 3 and rgb_u16.shape[2] == 3
    h, w, _ = rgb_u16.shape
    be = rgb_u16.astype(">u2").tobytes()
    stride = w * 6
    raw_rows = bytearray()
    for y in range(h):
        raw_rows.append(0)  # Filter type 0 (None)
        raw_rows.extend(be[y * stride : (y + 1) * stride])
    compressed = zlib.compress(bytes(raw_rows), level=6)

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", w, h, 16, 2, 0, 0, 0)
    png_bytes = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png_bytes)


def read_png_ihdr_and_pixels(path: str):
    """Verify bit depth, color type, dimensions, and decode 16-bit pixels from PNG."""
    with open(path, "rb") as f:
        data = f.read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos = 8
    idat = bytearray()
    ihdr_info = None
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        tag = data[pos + 4 : pos + 8]
        payload = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if tag == b"IHDR":
            ihdr_info = struct.unpack(">IIBBBBB", payload)
        elif tag == b"IDAT":
            idat.extend(payload)
        elif tag == b"IEND":
            break
    w, h, bit_depth, color_type, _, _, _ = ihdr_info
    raw = zlib.decompress(bytes(idat))
    row_bytes = 1 + w * 6
    arr = np.frombuffer(raw, dtype=np.uint8).reshape(h, row_bytes)
    assert np.all(arr[:, 0] == 0)
    pixels = np.frombuffer(arr[:, 1:].tobytes(), dtype=">u2").reshape(h, w, 3).astype(np.uint16)
    return ihdr_info, pixels


def build_test_chart():
    # Base background: neutral dark gray DI = 0.10
    canvas = np.full((H, W, 3), 0.10, dtype=np.float64)

    # Shared horizontal ramp coordinate: x in [190, 1860) maps DI from 0.00 to 0.55
    x0, x1 = 190, 1860
    ramp_w = x1 - x0
    di_axis = np.linspace(0.0, 0.55, ramp_w, dtype=np.float64)
    y_axis = di_to_linear(di_axis)

    # 1. Module 1: Neutral Gray Scale Ramp (y: 86..140)
    canvas[86:140, x0:x1, :] = di_axis[None, :, None]

    # 2. Module 2: 7 Equal-Luminance Color Ramps with 4px Equal-Luma Gray Borders (y: 164..534)
    bands = [
        ("Red", np.array([1.00, 0.06, 0.06])),
        ("Warm Skin", np.array([0.82, 0.44, 0.25])),
        ("Yellow", np.array([0.96, 0.90, 0.06])),
        ("Green", np.array([0.06, 0.96, 0.10])),
        ("Cyan", np.array([0.06, 0.88, 0.94])),
        ("Blue", np.array([0.06, 0.12, 1.00])),
        ("Magenta", np.array([0.92, 0.06, 0.90])),
    ]
    band_top = 164
    band_h = 46
    band_gap = 8
    band_y_positions = []

    for idx, (label, hue709) in enumerate(bands):
        yt = band_top + idx * (band_h + band_gap)
        yb = yt + band_h
        band_y_positions.append((yt, yb, label))

        # Top & bottom 4px equal-luminance neutral gray reference bars
        canvas[yt : yt + 4, x0:x1, :] = di_axis[None, :, None]
        canvas[yb - 4 : yb, x0:x1, :] = di_axis[None, :, None]

        # Color ramp (pixel-aligned to same CIE luminance Y as neutral gray ramp)
        rgb709_row = make_equal_luma_color_709(hue709, y_axis)
        dwg_di_row = rec709_lin_to_dwg_di(rgb709_row)
        canvas[yt + 4 : yb - 4, x0:x1, :] = dwg_di_row[None, :, :]

    # Subtle vertical reference markers at Floor=0.08, Pivot=0.28, MidGray=0.336
    for ref_di in [0.08, 0.28, 0.336043]:
        rx = x0 + int(round((ref_di / 0.55) * (ramp_w - 1)))
        canvas[80:86, rx : rx + 2, :] = 0.42
        canvas[140:158, rx : rx + 1, :] = 0.28

    # 3. Module 3 (Bottom Left, x: 50..630): Shadow Chroma Noise Stress Matrix (4 cols x 2 rows)
    rng = np.random.default_rng(2026)
    col_lumas = [0.04, 0.08, 0.12, 0.18]
    box_w, box_h = 134, 152
    col_gap = 14
    m3_x0 = 50
    row1_y0, row2_y0 = 626, 816

    def tile_noise_2x2(h, w, ch=3, sigma=1.0):
        nh, nw = (h + 1) // 2, (w + 1) // 2
        n = rng.normal(0.0, sigma, size=(nh, nw, ch))
        return np.repeat(np.repeat(n, 2, axis=0), 2, axis=1)[:h, :w, :]

    # Row 1: Mixed High-ISO RGB Chroma Noise at DI = 0.04, 0.08, 0.12, 0.18
    for c_idx, base_di in enumerate(col_lumas):
        bx0 = m3_x0 + c_idx * (box_w + col_gap)
        n_rgb = tile_noise_2x2(box_h, box_w, 3, sigma=0.048)
        # Zero-mean chroma component + slight luma grain
        n_chroma = n_rgb - np.mean(n_rgb, axis=-1, keepdims=True)
        patch = np.clip(base_di + n_chroma * 1.35 + tile_noise_2x2(box_h, box_w, 1, sigma=0.008), 0.0, 1.0)
        canvas[row1_y0 : row1_y0 + box_h, bx0 : bx0 + box_w, :] = patch

    # Row 2: Specialized Edge-Case Stress Patches
    # 2a. Green Noise (tests Chroma Density < 0 white-speck suppression)
    bx0 = m3_x0 + 0 * (box_w + col_gap)
    g_mask = (rng.uniform(0.0, 1.0, size=(box_h // 2, box_w // 2)) > 0.72).astype(np.float64)
    g_mask = np.repeat(np.repeat(g_mask, 2, axis=0), 2, axis=1)[:box_h, :box_w]
    g_amp = rng.uniform(0.04, 0.11, size=(box_h // 2, box_w // 2))
    g_amp = np.repeat(np.repeat(g_amp, 2, axis=0), 2, axis=1)[:box_h, :box_w]
    p2a = np.full((box_h, box_w, 3), 0.06, dtype=np.float64)
    p2a[:, :, 1] += g_mask * g_amp
    canvas[row2_y0 : row2_y0 + box_h, bx0 : bx0 + box_w, :] = np.clip(p2a, 0.0, 1.0)

    # 2b. Imaginary DWG Blue Noise (tests DWG negative-Y black-hole fix)
    bx0 = m3_x0 + 1 * (box_w + col_gap)
    b_mask = (rng.uniform(0.0, 1.0, size=(box_h // 2, box_w // 2)) > 0.55).astype(np.float64)
    b_mask = np.repeat(np.repeat(b_mask, 2, axis=0), 2, axis=1)[:box_h, :box_w]
    b_amp = rng.uniform(0.06, 0.17, size=(box_h // 2, box_w // 2))
    b_amp = np.repeat(np.repeat(b_amp, 2, axis=0), 2, axis=1)[:box_h, :box_w]
    p2b = np.full((box_h, box_w, 3), 0.03, dtype=np.float64)
    p2b[:, :, 0] = 0.005
    p2b[:, :, 1] = 0.005
    p2b[:, :, 2] = 0.02 + b_mask * b_amp
    canvas[row2_y0 : row2_y0 + box_h, bx0 : bx0 + box_w, :] = np.clip(p2b, 0.0, 1.0)

    # 2c. Magenta / Cyan Shadow Noise
    bx0 = m3_x0 + 2 * (box_w + col_gap)
    mc_sel = rng.uniform(0.0, 1.0, size=(box_h // 2, box_w // 2))
    mc_sel = np.repeat(np.repeat(mc_sel, 2, axis=0), 2, axis=1)[:box_h, :box_w]
    p2c = np.full((box_h, box_w, 3), 0.075, dtype=np.float64)
    p2c[:, :, 0] += np.where(mc_sel > 0.65, 0.085, np.where(mc_sel < 0.35, -0.04, 0.0))
    p2c[:, :, 1] += np.where(mc_sel > 0.65, -0.035, np.where(mc_sel < 0.35, 0.06, 0.0))
    p2c[:, :, 2] += np.where(mc_sel > 0.65, 0.085, np.where(mc_sel < 0.35, 0.075, 0.0))
    canvas[row2_y0 : row2_y0 + box_h, bx0 : bx0 + box_w, :] = np.clip(p2c, 0.0, 1.0)

    # 2d. Near-Zero Black Floor Micro-Noise (tests continuity near DI=0)
    bx0 = m3_x0 + 3 * (box_w + col_gap)
    n_floor = tile_noise_2x2(box_h, box_w, 3, sigma=0.018)
    p2d = np.clip(0.015 + n_floor, 0.0, 1.0)
    canvas[row2_y0 : row2_y0 + box_h, bx0 : bx0 + box_w, :] = p2d

    # 4. Module 4 (Bottom Center, x: 670..1250): Warm Skin Sphere vs Cool Blue Sphere over Shadow Noise
    m4_x0, m4_x1 = 670, 1250
    m4_y0, m4_y1 = 602, 990
    bg_noise = np.full((m4_y1 - m4_y0, m4_x1 - m4_x0, 3), 0.065, dtype=np.float64)
    n4 = tile_noise_2x2(m4_y1 - m4_y0, m4_x1 - m4_x0, 3, sigma=0.016)
    bg_noise += (n4 - np.mean(n4, axis=-1, keepdims=True)) * 1.4
    bg_noise[:, :, 2] += 0.012  # slight cool shadow cast
    canvas[m4_y0:m4_y1, m4_x0:m4_x1, :] = np.clip(bg_noise, 0.0, 1.0)

    yy, xx = np.mgrid[m4_y0:m4_y1, m4_x0:m4_x1]
    spheres = [
        (815.0, 782.0, 118.0, np.array([0.82, 0.44, 0.25])),   # Warm Skin (+48 deg)
        (1105.0, 782.0, 118.0, np.array([0.14, 0.34, 0.96])),  # Cool Blue Shadow
    ]
    for cx, cy, rad, hue in spheres:
        dx = (xx - cx) / rad
        dy = (yy - cy) / rad
        r2 = dx * dx + dy * dy
        inside = r2 <= 1.0
        nz = np.sqrt(np.maximum(1.0 - r2, 0.0))
        # Directional light from top-left (-0.45, -0.45, 0.77)
        ndotl = np.clip(-0.45 * dx - 0.45 * dy + 0.77 * nz, 0.0, 1.0)
        sphere_di = 0.045 + 0.315 * np.power(ndotl, 1.35)
        sphere_y = di_to_linear(sphere_di[inside])
        rgb709_s = make_equal_luma_color_709(hue, sphere_y, sat_factor=np.full_like(sphere_y, 0.88))
        dwg_di_s = rec709_lin_to_dwg_di(rgb709_s)
        patch_m4 = canvas[m4_y0:m4_y1, m4_x0:m4_x1, :]
        # Soft 1.5px anti-aliased edge
        edge_a = np.clip((1.0 - np.sqrt(r2)) * rad * 0.8, 0.0, 1.0)
        sub_inside = patch_m4[inside]
        patch_m4[inside] = sub_inside * (1.0 - edge_a[inside, None]) + dwg_di_s * edge_a[inside, None]

    # 5. Module 5 (Bottom Right, x: 1290..1870): Equal-Luma Vectorscope Color Wheel
    # Inner circle (r <= 122): DI = 0.14 (deep shadow); Outer ring (140 <= r <= 178): DI = 0.38 (untouched midtone)
    m5_x0, m5_x1 = 1290, 1870
    m5_y0, m5_y1 = 602, 990
    wy, wx = np.mgrid[m5_y0:m5_y1, m5_x0:m5_x1]
    wcx, wcy = 1580.0, 782.0
    wr = np.hypot(wx - wcx, wy - wcy)
    ang = np.arctan2(-(wy - wcy), wx - wcx)  # 0 at East, CCW

    # Map hue smoothly in [0, 1)
    h_frac = (ang / (2.0 * np.pi)) % 1.0
    # Vectorized HSV-like pure linear primaries sweep (R -> Y -> G -> C -> B -> M -> R)
    h6 = h_frac * 6.0
    sector = np.floor(h6).astype(np.int32) % 6
    f = h6 - np.floor(h6)
    p = np.zeros_like(f)
    q = 1.0 - f
    t = f
    hue_rgb = np.zeros((wy.shape[0], wy.shape[1], 3), dtype=np.float64)
    for sec, (rr, gg, bb) in [
        (0, (np.ones_like(f), t, p)),
        (1, (q, np.ones_like(f), p)),
        (2, (p, np.ones_like(f), t)),
        (3, (p, q, np.ones_like(f))),
        (4, (t, p, np.ones_like(f))),
        (5, (np.ones_like(f), p, q)),
    ]:
        m = sector == sec
        hue_rgb[m, 0] = rr[m]
        hue_rgb[m, 1] = gg[m]
        hue_rgb[m, 2] = bb[m]

    # Inner disk: DI = 0.14
    in_disk = wr <= 122.0
    sat_disk = np.clip(wr / 120.0, 0.0, 1.0)
    y_inner = np.full(np.sum(in_disk), di_to_linear(0.14), dtype=np.float64)
    y0_inner = 0.2126 * hue_rgb[in_disk, 0] + 0.7152 * hue_rgb[in_disk, 1] + 0.0722 * hue_rgb[in_disk, 2]
    # Keep saturation well within Rec.709 gamut at DI=0.14
    lin_inner = y_inner[:, None] + (hue_rgb[in_disk] * (y_inner / y0_inner)[:, None] - y_inner[:, None]) * sat_disk[in_disk, None]
    # Softly clamp into [0, 1] preserving Y
    under_i = np.min(lin_inner, axis=-1)
    if np.any(under_i < 0.0):
        denom = np.maximum(y_inner - under_i, 1e-8)
        t_fit = np.where(under_i < 0.0, np.clip(y_inner / denom, 0.0, 1.0), 1.0)
        lin_inner = y_inner[:, None] + (lin_inner - y_inner[:, None]) * t_fit[:, None]
    dwg_inner = rec709_lin_to_dwg_di(np.clip(lin_inner, 0.0, 1.0))

    wheel_patch = canvas[m5_y0:m5_y1, m5_x0:m5_x1, :]
    wheel_patch[in_disk] = dwg_inner

    # Outer ring: DI = 0.38 (untouched reference ring)
    in_outer = (wr >= 140.0) & (wr <= 178.0)
    y_outer = np.full(np.sum(in_outer), di_to_linear(0.38), dtype=np.float64)
    y0_outer = 0.2126 * hue_rgb[in_outer, 0] + 0.7152 * hue_rgb[in_outer, 1] + 0.0722 * hue_rgb[in_outer, 2]
    lin_outer = y_outer[:, None] + (hue_rgb[in_outer] * (y_outer / y0_outer)[:, None] - y_outer[:, None]) * 0.85
    # Fit into Rec.709 [0, 1] preserving Y
    max_o = np.max(lin_outer, axis=-1)
    if np.any(max_o > 1.0):
        denom = np.maximum(max_o - y_outer, 1e-8)
        t_fit = np.where(max_o > 1.0, np.clip((1.0 - y_outer) / denom, 0.0, 1.0), 1.0)
        lin_outer = y_outer[:, None] + (lin_outer - y_outer[:, None]) * t_fit[:, None]
    min_o = np.min(lin_outer, axis=-1)
    if np.any(min_o < 0.0):
        denom = np.maximum(y_outer - min_o, 1e-8)
        t_fit = np.where(min_o < 0.0, np.clip(y_outer / denom, 0.0, 1.0), 1.0)
        lin_outer = y_outer[:, None] + (lin_outer - y_outer[:, None]) * t_fit[:, None]
    dwg_outer = rec709_lin_to_dwg_di(np.clip(lin_outer, 0.0, 1.0))
    wheel_patch[in_outer] = dwg_outer

    # 6. Draw all annotations in DI = 0.42 pure neutral gray (above Pivot, legible in Rec.709)
    f_title = load_font(22)
    f_sub = load_font(17)
    f_small = load_font(15)

    def draw_labels(draw: ImageDraw.ImageDraw):
        # Top banner
        draw.text(
            (50, 16),
            "DWG / DAVINCI INTERMEDIATE SHADOW DESAT TEST CHART (16-BIT)   |   CST: DWG/DI -> REC.709 G2.4",
            fill=255,
            font=f_title,
        )
        # Left labels for Module 1 & 2
        draw.text((50, 102), "NEUTRAL GRAY", fill=255, font=f_sub)
        for yt, yb, label in band_y_positions:
            draw.text((50, yt + 14), label, fill=255, font=f_sub)

        # Scale ticks above Module 1
        ticks = [
            (0.00, "0.00"),
            (0.08, "0.08 Floor"),
            (0.15, "0.15"),
            (0.22, "0.22"),
            (0.28, "0.28 Pivot"),
            (0.336043, "0.336 (18%)"),
            (0.45, "0.45"),
            (0.55, "0.55"),
        ]
        for val, txt in ticks:
            tx = x0 + int(round((val / 0.55) * (ramp_w - 1)))
            anchor_x = tx if val < 0.50 else tx - 38
            if val == 0.28:
                anchor_x = tx - 36
            elif val == 0.336043:
                anchor_x = tx + 4
            draw.text((anchor_x, 56), txt, fill=255, font=f_small)

        # Bottom Section Headers
        draw.text((50, 566), "SHADOW CHROMA NOISE MATRIX", fill=255, font=f_sub)
        draw.text((670, 566), "WARM SKIN PROTECT vs COOL SHADOWS", fill=255, font=f_sub)
        draw.text((1290, 566), "EQUAL-LUMA WHEEL (IN: DI 0.14 | OUT: DI 0.38)", fill=255, font=f_sub)

        # Module 3 labels
        for c_idx, base_di in enumerate(col_lumas):
            bx0 = m3_x0 + c_idx * (box_w + col_gap)
            draw.text((bx0 + 24, 600), f"RGB DI={base_di:.2f}", fill=255, font=f_small)

        row2_labels = ["Green Noise", "DWG Blue", "Mag / Cyan", "Near-0 Floor"]
        for c_idx, txt in enumerate(row2_labels):
            bx0 = m3_x0 + c_idx * (box_w + col_gap)
            draw.text((bx0 + 14, row2_y0 + box_h + 8), txt, fill=255, font=f_small)

        # Module 4 labels
        draw.text((736, 922), "Warm Skin (+48 deg)", fill=255, font=f_small)
        draw.text((1034, 922), "Cool Blue Shadow", fill=255, font=f_small)

        # Module 5 labels
        draw.text((1350, 968), "Inner: -3EV Shadow | Outer: Untouched Midtone", fill=255, font=f_small)

        # Footer
        draw.text(
            (50, 1038),
            "TEST GUIDE: 1) Check Neutral Gray stability on Waveform   2) Compare Color vs 4px Gray Borders   3) Check Vectorscope straight radial pull (OkLab vs HSL)",
            fill=220,
            font=f_small,
        )

    draw_text_layer(canvas, draw_labels, text_di=0.42)

    # Borders around bottom 3 modules for clean visual separation
    def draw_borders(draw: ImageDraw.ImageDraw):
        for bx0, by0, bx1, by1 in [(670, 602, 1250, 990), (1290, 602, 1870, 990)]:
            draw.rectangle([bx0, by0, bx1, by1], outline=180, width=1)

    draw_text_layer(canvas, draw_borders, text_di=0.22)

    # Quantize to true 16-bit full-range PNG
    canvas_clipped = np.clip(canvas, 0.0, 1.0)
    rgb_u16 = np.round(canvas_clipped * 65535.0).astype(np.uint16)

    out_png = str(ROOT_DIR / "DWG_DI_Shadow_Desat_TestChart_16bit.png")
    preview_png = str(ROOT_DIR / "tests" / "preview_rec709.png")

    write_png_16bit_rgb(out_png, rgb_u16)

    # Save simulated Rec.709 8-bit preview for visual inspection
    disp709 = dwg_di_to_rec709_display(canvas_clipped)
    disp_u8 = np.round(np.clip(disp709, 0.0, 1.0) * 255.0).astype(np.uint8)
    Image.fromarray(disp_u8, mode="RGB").save(preview_png)

    # Self-verify written 16-bit PNG
    ihdr, decoded = read_png_ihdr_and_pixels(out_png)
    w_chk, h_chk, bpp, ctype, _, _, _ = ihdr
    assert (w_chk, h_chk) == (W, H), f"Unexpected dimensions: {(w_chk, h_chk)}"
    assert bpp == 16 and ctype == 2, f"Expected 16-bit RGB PNG, got bit_depth={bpp}, color_type={ctype}"
    assert decoded.dtype == np.uint16 and decoded.shape == (H, W, 3)

    # Verify 18% mid-gray ramp pixel accuracy
    mid_x = x0 + int(round((0.336043 / 0.55) * (ramp_w - 1)))
    measured_mid = decoded[110, mid_x]
    expected_mid = int(round((di_axis[mid_x - x0]) * 65535.0))
    assert np.max(np.abs(measured_mid.astype(np.int32) - expected_mid)) <= 1
    print(f"Generated 16-bit DWG/DI test chart: {out_png}")
    print(f"Verified PNG IHDR: {w_chk}x{h_chk}, bit_depth={bpp}, color_type={ctype}, file_size={os.path.getsize(out_png):,} bytes")
    print(f"Mid-gray ramp sample at x={mid_x}: u16={measured_mid.tolist()} (DI={measured_mid[0]/65535.0:.6f})")
    print(f"Generated Rec.709 simulated preview: {preview_png}")


if __name__ == "__main__":
    build_test_chart()
