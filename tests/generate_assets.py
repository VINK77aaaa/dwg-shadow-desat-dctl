"""
Regenerate visual assets in assets/ (banner.svg, rolloff_curves.svg, warm_skin_polar.svg,
and comparison_rec709.png) directly from the current DWG_Shadow_Desat mathematical model
and the 16-bit DWG/DI test chart.
"""

import math
import os
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import generate_test_chart as gtc
import verify_dctl as vd

ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "assets"


def write_lf_text(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


def generate_banner_svg() -> None:
    wheel_paths = []
    cx, cy = 175.0, 160.0
    r_out, r_in = 96.0, 72.0
    n_seg = 36
    # Subtle desaturated teal-blue-violet outer palette matching original visual emblem
    colors = [
        "#f21a1a", "#f23e1a", "#f2621a", "#f2861a", "#f2aa1a", "#f2ce1a",
        "#f2f21a", "#cef21a", "#aaf21a", "#86f21a", "#60e51e", "#41d025",
        "#2cb72c", "#32a044", "#378b53", "#3a7a5a", "#3c6e5e", "#3d6760",
        "#3d6565", "#3d6067", "#3c5e6e", "#3a5a7a", "#37538b", "#3244a0",
        "#2c2cb7", "#4125d0", "#601ee5", "#861af2", "#aa1af2", "#ce1af2",
        "#f21af2", "#f21ace", "#f21aaa", "#f21a86", "#f21a62", "#f21a3e",
    ]
    for i in range(n_seg):
        a0 = math.radians(i * (360.0 / n_seg) - 90.0)
        a1 = math.radians((i + 1) * (360.0 / n_seg) - 90.0 + 0.6)
        x1, y1 = cx + r_out * math.cos(a0), cy + r_out * math.sin(a0)
        x2, y2 = cx + r_out * math.cos(a1), cy + r_out * math.sin(a1)
        x3, y3 = cx + r_in * math.cos(a1), cy + r_in * math.sin(a1)
        x4, y4 = cx + r_in * math.cos(a0), cy + r_in * math.sin(a0)
        wheel_paths.append(
            f'    <path d="M {x1:.2f} {y1:.2f} A 96 96 0 0 1 {x2:.2f} {y2:.2f} '
            f'L {x3:.2f} {y3:.2f} A 72 72 0 0 0 {x4:.2f} {y4:.2f} Z" fill="{colors[i]}" />'
        )

    # Inner smooth5 curve icon points
    pts = []
    for k in range(41):
        u = k / 40.0
        w = u * u * u * (u * (u * 6.0 - 15.0) + 10.0)
        px = 133.0 + u * 84.0
        py = 190.0 - w * 60.0
        pts.append(f"{px:.1f},{py:.1f}")
    curve_d = "M " + " L ".join(pts)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 320" width="1200" height="320" role="img" aria-label="DWG Shadow Desat DCTL Banner">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0b0f17" />
      <stop offset="55%" stop-color="#111827" />
      <stop offset="100%" stop-color="#0d131f" />
    </linearGradient>
    <radialGradient id="glowLeft" cx="18%" cy="50%" r="45%">
      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.16" />
      <stop offset="50%" stop-color="#f59e0b" stop-opacity="0.06" />
      <stop offset="100%" stop-color="#0b0f17" stop-opacity="0" />
    </radialGradient>
    <linearGradient id="titleGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#f8fafc" />
      <stop offset="70%" stop-color="#e2e8f0" />
      <stop offset="100%" stop-color="#94a3b8" />
    </linearGradient>
    <linearGradient id="curveGrad" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#64748b" />
      <stop offset="55%" stop-color="#38bdf8" />
      <stop offset="100%" stop-color="#f59e0b" />
    </linearGradient>
    <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
      <path d="M 32 0 L 0 0 0 32" fill="none" stroke="#1e293b" stroke-width="0.7" stroke-opacity="0.55" />
    </pattern>
  </defs>

  <!-- Card Background -->
  <rect x="2" y="2" width="1196" height="316" rx="18" fill="url(#bgGrad)" stroke="#30363d" stroke-width="2" />
  <rect x="2" y="2" width="1196" height="316" rx="18" fill="url(#grid)" />
  <rect x="2" y="2" width="1196" height="316" rx="18" fill="url(#glowLeft)" />

  <!-- Subtle Waveform Accent on Right -->
  <path d="M 760 275 C 830 275, 860 245, 920 190 C 980 135, 1040 85, 1145 70" fill="none" stroke="#38bdf8" stroke-opacity="0.12" stroke-width="2" />
  <path d="M 760 285 C 850 285, 895 255, 960 205 C 1020 155, 1075 110, 1145 95" fill="none" stroke="#f59e0b" stroke-opacity="0.10" stroke-width="2" />

  <!-- Left Vector Emblem: DWG Color Wheel converging to Shadow Neutral Gray -->
  <g>
    <circle cx="175" cy="160" r="110" fill="#090d14" stroke="#1e293b" stroke-width="1.5" />
{chr(10).join(wheel_paths)}
    <!-- Inner Neutral Shadow Core -->
    <circle cx="175" cy="160" r="62" fill="#111620" stroke="#334155" stroke-width="1.5" />
    <!-- Pivot Line & C2 Smooth5 Rolloff Curve -->
    <line x1="131" y1="160" x2="219" y2="160" stroke="#334155" stroke-width="1" stroke-dasharray="3,3" />
    <path d="{curve_d}" fill="none" stroke="url(#curveGrad)" stroke-width="3.2" stroke-linecap="round" />
    <circle cx="133" cy="190" r="3.5" fill="#94a3b8" />
    <circle cx="217" cy="130" r="3.5" fill="#f59e0b" />
    <!-- Subtle Label in Emblem -->
    <text x="175" y="208" text-anchor="middle" fill="#64748b" font-family="Consolas, 'Courier New', monospace" font-size="10" letter-spacing="1.2">DWG / DI</text>
  </g>

  <!-- Main Title & Subtitle -->
  <g transform="translate(328, 86)">
    <rect x="0" y="-30" width="224" height="24" rx="12" fill="#1e293b" stroke="#38bdf8" stroke-opacity="0.45" stroke-width="1" />
    <text x="112" y="-14" text-anchor="middle" fill="#7dd3fc" font-family="Segoe UI, Arial, sans-serif" font-size="11.5" font-weight="600" letter-spacing="0.8">DAVINCI RESOLVE STUDIO · DCTL</text>

    <text x="0" y="34" fill="url(#titleGrad)" font-family="Segoe UI, -apple-system, BlinkMacSystemFont, sans-serif" font-size="48" font-weight="800" letter-spacing="-0.5">DWG Shadow Desat</text>
    <text x="2" y="70" fill="#94a3b8" font-family="Segoe UI, -apple-system, sans-serif" font-size="18.5" font-weight="400">
      专为 <tspan fill="#e2e8f0" font-weight="600">DaVinci Wide Gamut / Intermediate</tspan> 设计的暗部消色与胶片衰减插件
    </text>
    <text x="2" y="98" fill="#64748b" font-family="Consolas, 'Courier New', monospace" font-size="12.8">
      L2 Monotonic Mask · Blue-Inset OkLab · C2 Rational Smooth · Apple Silicon Metal &amp; 3D LUT Safe
    </text>

    <!-- Feature Pills -->
    <g transform="translate(0, 126)">
      <rect x="0" y="0" width="166" height="32" rx="16" fill="#0f172a" stroke="#38bdf8" stroke-opacity="0.55" stroke-width="1.2" />
      <circle cx="18" cy="16" r="4.5" fill="#38bdf8" />
      <text x="31" y="21" fill="#e0f2fe" font-family="Segoe UI, Arial, sans-serif" font-size="13" font-weight="600">Blue-Inset OkLab</text>

      <rect x="180" y="0" width="144" height="32" rx="16" fill="#0f172a" stroke="#34d399" stroke-opacity="0.55" stroke-width="1.2" />
      <circle cx="198" cy="16" r="4.5" fill="#34d399" />
      <text x="211" y="21" fill="#d1fae5" font-family="Segoe UI, Arial, sans-serif" font-size="13" font-weight="600">广色域零黑洞</text>

      <rect x="338" y="0" width="184" height="32" rx="16" fill="#0f172a" stroke="#f59e0b" stroke-opacity="0.55" stroke-width="1.2" />
      <circle cx="356" cy="16" r="4.5" fill="#f59e0b" />
      <text x="369" y="21" fill="#fef3c7" font-family="Segoe UI, Arial, sans-serif" font-size="13" font-weight="600">Warm Skin Protect</text>

      <rect x="536" y="0" width="164" height="32" rx="16" fill="#0f172a" stroke="#a78bfa" stroke-opacity="0.55" stroke-width="1.2" />
      <circle cx="554" cy="16" r="4.5" fill="#a78bfa" />
      <text x="567" y="21" fill="#ede9fe" font-family="Segoe UI, Arial, sans-serif" font-size="13" font-weight="600">33/65-pt LUT Safe</text>
    </g>
  </g>
</svg>
"""
    write_lf_text(ASSETS_DIR / "banner.svg", svg)


def generate_rolloff_svg() -> None:
    x_left, y_bot = 76.0, 362.0
    plot_w, plot_h = 850.0, 298.0
    x_max = 0.42
    pivot, floor = 0.28, 0.08

    def x_pos(val: float) -> float:
        return x_left + (val / x_max) * plot_w

    luma_vals = np.linspace(0.0, x_max, 211, dtype=np.float64)
    curve_specs = [
        (0.50, "#f59e0b", ""),
        (1.00, "#38bdf8", ""),
        (1.60, "#a78bfa", ""),
        (2.20, "#fb7185", ' stroke-dasharray="6,4"'),
    ]

    curve_paths = []
    for r, color, dash in curve_specs:
        t = np.clip((pivot - luma_vals) / (pivot - floor), 0.0, 1.0)
        ts = t / (t + r * (1.0 - t))
        w = ts ** 3 * (ts * (ts * 6.0 - 15.0) + 10.0)
        coords = [f"{x_pos(float(lv)):.1f},{y_bot - float(wv) * plot_h:.1f}" for lv, wv in zip(luma_vals, w)]
        curve_paths.append(
            f'  <path d="M {" L ".join(coords)}" fill="none" stroke="{color}" stroke-width="2.8" stroke-linecap="round"{dash} />'
        )

    x_floor = x_pos(floor)
    x_pivot = x_pos(pivot)
    x_mid = x_pos(0.336043)

    y_grid_lines = []
    for frac, lbl in [(0.0, "0.00"), (0.25, "0.25"), (0.50, "0.50"), (0.75, "0.75"), (1.0, "1.00")]:
        yy = y_bot - frac * plot_h
        y_grid_lines.append(
            f'  <line x1="76" y1="{yy:.1f}" x2="926" y2="{yy:.1f}" stroke="#1e293b" stroke-width="1" />\n'
            f'  <text x="66" y="{yy + 4:.1f}" text-anchor="end" fill="#94a3b8" font-family="Consolas, monospace" font-size="11.5">{lbl}</text>'
        )

    x_grid_lines = []
    for val, lbl in [(0.0, "0.00"), (0.08, "0.08"), (0.16, "0.16"), (0.24, "0.24"), (0.28, "0.28"), (0.336043, "0.336"), (0.40, "0.40")]:
        xx = x_pos(val)
        x_grid_lines.append(
            f'  <line x1="{xx:.1f}" y1="64" x2="{xx:.1f}" y2="362" stroke="#1e293b" stroke-width="1" />\n'
            f'  <text x="{xx:.1f}" y="380" text-anchor="middle" fill="#94a3b8" font-family="Consolas, monospace" font-size="11">{lbl}</text>'
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 420" width="960" height="420" role="img" aria-label="Shadow Rolloff Curves in DI Code Value Domain">
  <rect x="1" y="1" width="958" height="418" rx="12" fill="#0d1117" stroke="#30363d" stroke-width="1.5" />

  <!-- Header -->
  <text x="76" y="30" fill="#f8fafc" font-family="Segoe UI, Arial, sans-serif" font-size="17" font-weight="700">暗部消色衰减曲线（DI 编码域 · 有理 C² / Smooth5 平滑过渡）</text>
  <text x="76" y="49" fill="#8b949e" font-family="Consolas, monospace" font-size="12">Shadow Pivot = 0.28 | Black Floor = 0.08 | 18% Mid Gray ≈ 0.336 | Rational Schlick + Smooth5</text>

  <!-- Zone Shaded Backgrounds -->
  <rect x="76" y="64" width="{x_floor - x_left:.1f}" height="298" fill="#38bdf8" fill-opacity="0.06" />
  <rect x="{x_floor:.1f}" y="64" width="{x_pivot - x_floor:.1f}" height="298" fill="#a78bfa" fill-opacity="0.04" />
  <rect x="{x_pivot:.1f}" y="64" width="{926.0 - x_pivot:.1f}" height="298" fill="#22c55e" fill-opacity="0.05" />

  <!-- Zone Titles -->
  <text x="{(x_left + x_floor) / 2:.1f}" y="82" text-anchor="middle" fill="#7dd3fc" font-family="Segoe UI, Arial, sans-serif" font-size="11.5" font-weight="600">满额消色区</text>
  <text x="{(x_floor + x_pivot) / 2:.1f}" y="82" text-anchor="middle" fill="#c4b5fd" font-family="Segoe UI, Arial, sans-serif" font-size="11.5" font-weight="600">平滑滚落过渡区</text>
  <text x="{(x_pivot + 926.0) / 2:.1f}" y="82" text-anchor="middle" fill="#86efac" font-family="Segoe UI, Arial, sans-serif" font-size="11.5" font-weight="600">100% 透传区</text>

  <!-- Axes & Grid -->
{chr(10).join(y_grid_lines)}
{chr(10).join(x_grid_lines)}
  <rect x="76" y="64" width="850" height="298" fill="none" stroke="#334155" stroke-width="1.2" />

  <!-- Reference Vertical Lines -->
  <line x1="{x_floor:.1f}" y1="64" x2="{x_floor:.1f}" y2="362" stroke="#38bdf8" stroke-width="1.3" stroke-dasharray="5,4" />
  <text x="{x_floor + 5:.1f}" y="352" fill="#7dd3fc" font-family="Segoe UI, Arial, sans-serif" font-size="11">Black Floor (0.08)</text>

  <line x1="{x_pivot:.1f}" y1="64" x2="{x_pivot:.1f}" y2="362" stroke="#a78bfa" stroke-width="1.3" stroke-dasharray="5,4" />
  <text x="{x_pivot - 6:.1f}" y="100" text-anchor="end" fill="#c4b5fd" font-family="Segoe UI, Arial, sans-serif" font-size="11">Shadow Pivot (0.28)</text>

  <line x1="{x_mid:.1f}" y1="64" x2="{x_mid:.1f}" y2="362" stroke="#22c55e" stroke-width="1.3" stroke-dasharray="3,4" />
  <text x="{x_mid + 5:.1f}" y="118" fill="#86efac" font-family="Segoe UI, Arial, sans-serif" font-size="11">18% 中灰 (0.336)</text>

  <!-- Rolloff Curves -->
{chr(10).join(curve_paths)}

  <!-- Axis Titles -->
  <text x="501.0" y="406" text-anchor="middle" fill="#cbd5e1" font-family="Segoe UI, Arial, sans-serif" font-size="12.5" font-weight="600">L2 感知亮度对应的 DaVinci Intermediate 码值 (luma_di)</text>
  <text x="20" y="213.0" text-anchor="middle" transform="rotate(-90 20 213.0)" fill="#cbd5e1" font-family="Segoe UI, Arial, sans-serif" font-size="12.5" font-weight="600">暗部消色权重 (w_shadow)</text>

  <!-- Legend Box -->
  <rect x="681" y="80" width="234" height="114" rx="8" fill="#161b22" fill-opacity="0.92" stroke="#30363d" stroke-width="1" />
    <line x1="693" y1="98" x2="721" y2="98" stroke="#f59e0b" stroke-width="2.8" /><text x="729" y="102" fill="#e2e8f0" font-family="Segoe UI, Arial, sans-serif" font-size="12">Rolloff = 0.50（胶片早滚落）</text>
    <line x1="693" y1="122" x2="721" y2="122" stroke="#38bdf8" stroke-width="2.8" /><text x="729" y="126" fill="#e2e8f0" font-family="Segoe UI, Arial, sans-serif" font-size="12">Rolloff = 1.00（默认均衡）</text>
    <line x1="693" y1="146" x2="721" y2="146" stroke="#a78bfa" stroke-width="2.8" /><text x="729" y="150" fill="#e2e8f0" font-family="Segoe UI, Arial, sans-serif" font-size="12">Rolloff = 1.60（陡峭压底噪）</text>
    <line x1="693" y1="170" x2="721" y2="170" stroke="#fb7185" stroke-width="2.8" stroke-dasharray="6,4" /><text x="729" y="174" fill="#e2e8f0" font-family="Segoe UI, Arial, sans-serif" font-size="12">Rolloff = 2.20（极暗收拢）</text>
</svg>
"""
    write_lf_text(ASSETS_DIR / "rolloff_curves.svg", svg)


def _oklab_ring_hex(theta_rad: float) -> str:
    """Convert OkLab angle at modest chroma (L=0.72, C=0.11) into sRGB hex for ring legend."""
    L = 0.72
    a = 0.11 * math.cos(theta_rad)
    b = 0.11 * math.sin(theta_rad)
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bl = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    vals = []
    for ch in (r, g, bl):
        c = max(0.0, min(1.0, ch))
        sr = 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1.0 / 2.4)) - 0.055
        vals.append(int(round(max(0.0, min(1.0, sr)) * 255)))
    return f"#{vals[0]:02x}{vals[1]:02x}{vals[2]:02x}"


def generate_warm_skin_svg() -> None:
    cx, cy = 235.0, 222.0
    r_max = 142.0
    sigma_r_sq = 0.0030
    target_deg = 48.0

    ring_paths = []
    n_seg = 90
    for i in range(n_seg):
        t0 = math.radians(i * 4.0)
        t1 = math.radians((i + 1) * 4.0 + 0.25)
        tm = 0.5 * (t0 + t1)
        hex_col = _oklab_ring_hex(tm)
        x1, y1 = cx + 154.0 * math.cos(t0), cy - 154.0 * math.sin(t0)
        x2, y2 = cx + 154.0 * math.cos(t1), cy - 154.0 * math.sin(t1)
        x3, y3 = cx + 144.0 * math.cos(t1), cy - 144.0 * math.sin(t1)
        x4, y4 = cx + 144.0 * math.cos(t0), cy - 144.0 * math.sin(t0)
        ring_paths.append(
            f'  <path d="M {x1:.1f} {y1:.1f} A 154 154 0 0 0 {x2:.1f} {y2:.1f} '
            f'L {x3:.1f} {y3:.1f} A 144 144 0 0 1 {x4:.1f} {y4:.1f} Z" fill="{hex_col}" opacity="0.88" />'
        )

    def warm_w_func(deg: float, rc_ratio_sq: float) -> float:
        p = max(math.cos(math.radians(deg - target_deg)), 0.0)
        return (p * p) / (1.0 + sigma_r_sq / rc_ratio_sq)

    def polar_path(protect: float, rc_ratio_sq: float) -> str:
        pts = []
        for k in range(181):
            deg = k * 2.0
            rad = math.radians(deg)
            rem = 1.0 - protect * warm_w_func(deg, rc_ratio_sq)
            rr = rem * r_max
            pts.append(f"{cx + rr * math.cos(rad):.1f},{cy - rr * math.sin(rad):.1f}")
        return "M " + " L ".join(pts) + " Z"

    def cart_path(protect: float, rc_ratio_sq: float) -> str:
        pts = []
        for k in range(181):
            deg = k * 2.0
            rem = 1.0 - protect * warm_w_func(deg, rc_ratio_sq)
            px = 465.0 + (deg / 360.0) * 450.0
            py = 318.0 - rem * 210.0
            pts.append(f"{px:.1f},{py:.1f}")
        return "M " + " L ".join(pts)

    ax_rad = math.radians(target_deg)
    ax_x = cx + (r_max + 18.0) * math.cos(ax_rad)
    ax_y = cy - (r_max + 18.0) * math.sin(ax_rad)

    p_zero_polar = polar_path(0.0, 1e6)
    p_half_polar = polar_path(0.50, 1e6)
    p_full_polar = polar_path(1.00, 1e6)
    p_midc_polar = polar_path(1.00, sigma_r_sq)

    p_full_cart = cart_path(1.00, 1e6)
    p_midc_cart = cart_path(1.00, sigma_r_sq)
    p_half_cart = cart_path(0.50, 1e6)
    p_zero_cart = cart_path(0.00, 1e6)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 420" width="960" height="420" role="img" aria-label="Warm Skin Protect Polar Response">
  <rect x="1" y="1" width="958" height="418" rx="12" fill="#0d1117" stroke="#30363d" stroke-width="1.5" />

  <!-- Header -->
  <text x="34" y="30" fill="#f8fafc" font-family="Segoe UI, Arial, sans-serif" font-size="17" font-weight="700">OkLab 暖调 / 肤色定向保护机制（Warm Skin Protect）</text>
  <text x="34" y="49" fill="#8b949e" font-family="Consolas, monospace" font-size="11.5">Target Hue = +48° in OkLab (a, b) | Lorentzian-Regularized cos² Bell (σr = 0.055, Luma-Invariant) | Zero Clipping</text>

  <!-- Polar Grid -->
  <circle cx="235" cy="222" r="71.0" fill="none" stroke="#1e293b" stroke-width="1" stroke-dasharray="3,3" />
  <circle cx="235" cy="222" r="142" fill="none" stroke="#1e293b" stroke-width="1" />
  <line x1="87" y1="222" x2="383" y2="222" stroke="#1e293b" stroke-width="1" />
  <line x1="235" y1="74" x2="235" y2="370" stroke="#1e293b" stroke-width="1" />

  <!-- OkLab Hue Ring -->
{chr(10).join(ring_paths)}

  <!-- +48 deg Axis -->
  <line x1="235" y1="222" x2="{ax_x:.1f}" y2="{ax_y:.1f}" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="4,3" />
  <circle cx="{ax_x:.1f}" cy="{ax_y:.1f}" r="4" fill="#f59e0b" />
  <text x="{ax_x + 8:.1f}" y="{ax_y - 4:.1f}" fill="#fbbf24" font-family="Segoe UI, Arial, sans-serif" font-size="11.5" font-weight="600">+48° 暖肤保护中心</text>

  <!-- Polar Envelopes (remaining desaturation ratio) -->
  <path d="{p_zero_polar}" fill="none" stroke="#64748b" stroke-width="2.5" stroke-dasharray="4,4" />
  <path d="{p_half_polar}" fill="none" stroke="#38bdf8" stroke-width="2.5" />
  <path d="{p_full_polar}" fill="#f59e0b" fill-opacity="0.08" stroke="#f59e0b" stroke-width="2.5" />
  <path d="{p_midc_polar}" fill="none" stroke="#fbbf24" stroke-width="1.6" stroke-dasharray="3,3" opacity="0.75" />
  <text x="235" y="226" text-anchor="middle" fill="#94a3b8" font-family="Segoe UI, Arial, sans-serif" font-size="11">0% 消色</text>
  <text x="90.4" y="318.0" text-anchor="middle" fill="#7dd3fc" font-family="Segoe UI, Arial, sans-serif" font-size="11">冷/绿/青彩噪 100% 消色</text>

  <!-- Right Cartesian Chart -->
  <text x="465" y="94" fill="#e2e8f0" font-family="Segoe UI, Arial, sans-serif" font-size="13.5" font-weight="600">各色相角度剩余消色比例（1 - Warm Protect × warm_w）</text>
  <rect x="465.0" y="108" width="172.5" height="210" fill="#f59e0b" fill-opacity="0.06" />
  <rect x="862.5" y="108" width="52.5" height="210" fill="#f59e0b" fill-opacity="0.06" />
  <line x1="465" y1="318.0" x2="915" y2="318.0" stroke="#1e293b" stroke-width="1" />
  <text x="457" y="322.0" text-anchor="end" fill="#94a3b8" font-family="Consolas, monospace" font-size="11">0%</text>
  <line x1="465" y1="213.0" x2="915" y2="213.0" stroke="#1e293b" stroke-width="1" />
  <text x="457" y="217.0" text-anchor="end" fill="#94a3b8" font-family="Consolas, monospace" font-size="11">50%</text>
  <line x1="465" y1="108.0" x2="915" y2="108.0" stroke="#1e293b" stroke-width="1" />
  <text x="457" y="112.0" text-anchor="end" fill="#94a3b8" font-family="Consolas, monospace" font-size="11">100%</text>
  <line x1="465.0" y1="108" x2="465.0" y2="318" stroke="#1e293b" stroke-width="1" />
  <text x="465.0" y="334" text-anchor="middle" fill="#94a3b8" font-family="Consolas, monospace" font-size="10.5">0°</text>
  <line x1="525.0" y1="108" x2="525.0" y2="318" stroke="#1e293b" stroke-width="1" />
  <text x="525.0" y="334" text-anchor="middle" fill="#fbbf24" font-family="Consolas, monospace" font-size="10.5">48°</text>
  <line x1="615.0" y1="108" x2="615.0" y2="318" stroke="#1e293b" stroke-width="1" />
  <text x="615.0" y="334" text-anchor="middle" fill="#94a3b8" font-family="Consolas, monospace" font-size="10.5">120°</text>
  <line x1="690.0" y1="108" x2="690.0" y2="318" stroke="#1e293b" stroke-width="1" />
  <text x="690.0" y="334" text-anchor="middle" fill="#94a3b8" font-family="Consolas, monospace" font-size="10.5">180°</text>
  <line x1="765.0" y1="108" x2="765.0" y2="318" stroke="#1e293b" stroke-width="1" />
  <text x="765.0" y="334" text-anchor="middle" fill="#94a3b8" font-family="Consolas, monospace" font-size="10.5">240°</text>
  <line x1="840.0" y1="108" x2="840.0" y2="318" stroke="#1e293b" stroke-width="1" />
  <text x="840.0" y="334" text-anchor="middle" fill="#94a3b8" font-family="Consolas, monospace" font-size="10.5">300°</text>
  <line x1="915.0" y1="108" x2="915.0" y2="318" stroke="#1e293b" stroke-width="1" />
  <text x="915.0" y="334" text-anchor="middle" fill="#94a3b8" font-family="Consolas, monospace" font-size="10.5">360°</text>
  <rect x="465" y="108" width="450" height="210" fill="none" stroke="#334155" stroke-width="1.2" />
  <line x1="525.0" y1="108" x2="525.0" y2="318" stroke="#f59e0b" stroke-width="1.2" stroke-dasharray="4,3" />
  <path d="{p_full_cart}" fill="none" stroke="#f59e0b" stroke-width="2.5" />
  <path d="{p_midc_cart}" fill="none" stroke="#fbbf24" stroke-width="1.7" stroke-dasharray="3,3" opacity="0.8" />
  <path d="{p_half_cart}" fill="none" stroke="#38bdf8" stroke-width="2.5" />
  <path d="{p_zero_cart}" fill="none" stroke="#64748b" stroke-width="2.5" stroke-dasharray="4,4" />

  <!-- Right Legend -->
  <g transform="translate(455, 352)">
    <line x1="0" y1="6" x2="20" y2="6" stroke="#f59e0b" stroke-width="2.5" />
    <text x="25" y="10" fill="#fde68a" font-family="Segoe UI, Arial, sans-serif" font-size="11">Protect = 1.00 (C/L≫σr)</text>

    <line x1="168" y1="6" x2="188" y2="6" stroke="#fbbf24" stroke-width="1.7" stroke-dasharray="3,3" />
    <text x="193" y="10" fill="#fcd34d" font-family="Segoe UI, Arial, sans-serif" font-size="11">C/L = σr (0.055)</text>

    <line x1="296" y1="6" x2="316" y2="6" stroke="#38bdf8" stroke-width="2.5" />
    <text x="321" y="10" fill="#bae6fd" font-family="Segoe UI, Arial, sans-serif" font-size="11">Protect = 0.50</text>

    <line x1="406" y1="6" x2="426" y2="6" stroke="#64748b" stroke-width="2.5" stroke-dasharray="4,4" />
    <text x="431" y="10" fill="#cbd5e1" font-family="Segoe UI, Arial, sans-serif" font-size="11">0.00</text>
  </g>
</svg>
"""
    write_lf_text(ASSETS_DIR / "warm_skin_polar.svg", svg)


def generate_comparison_png() -> None:
    chart_path = ROOT_DIR / "DWG_DI_Shadow_Desat_TestChart_16bit.png"
    _, pixels_u16 = gtc.read_png_ihdr_and_pixels(str(chart_path))
    di_img = (pixels_u16.astype(np.float32) / 65535.0)

    panels = [
        (
            "1. Original Test Chart (DWG/DI -> Rec.709 G2.4)",
            di_img,
        ),
        (
            "2. Film Rolloff Preset (OkLab | Strength 0.85 | Warm Protect 0.20)",
            vd.dctl_transform(
                di_img,
                desat_engine=vd.ENGINE_OKLAB,
                desat_strength=0.85,
                shadow_pivot=0.28,
                black_floor=0.08,
                rolloff_curve=1.0,
                chroma_density=-0.08,
                warm_protect=0.20,
                preview_mode=vd.PREVIEW_OFF,
            ),
        ),
        (
            "3. Highlight Preview (Warm Skin Protect = 0.80 -> Mid Gray = Protected)",
            vd.dctl_transform(
                di_img,
                desat_engine=vd.ENGINE_OKLAB,
                desat_strength=0.85,
                shadow_pivot=0.28,
                black_floor=0.08,
                rolloff_curve=1.0,
                chroma_density=-0.08,
                warm_protect=0.80,
                preview_mode=vd.PREVIEW_HIGHLIGHT,
            ),
        ),
        (
            "4. Shadow Mask Preview (Desat Strength 0.85 | Warm Protect = 0.80)",
            vd.dctl_transform(
                di_img,
                desat_engine=vd.ENGINE_OKLAB,
                desat_strength=0.85,
                shadow_pivot=0.28,
                black_floor=0.08,
                rolloff_curve=1.0,
                chroma_density=-0.08,
                warm_protect=0.80,
                preview_mode=vd.PREVIEW_MASK,
            ),
        ),
    ]

    # Match 1646 x 1014 grid layout
    tile_w, tile_h = 798, 449
    hdr_h = 33
    card_w, card_h = tile_w + 2, hdr_h + tile_h + 2
    pad = 16
    gap = 14
    canvas_w = pad * 2 + card_w * 2 + gap
    canvas_h = pad * 2 + card_h * 2 + gap

    canvas = Image.new("RGB", (canvas_w, canvas_h), (13, 17, 23))
    draw = ImageDraw.Draw(canvas)
    font = gtc.load_font(16)

    for idx, (title, di_arr) in enumerate(panels):
        row, col = divmod(idx, 2)
        x0 = pad + col * (card_w + gap)
        y0 = pad + row * (card_h + gap)

        draw.rectangle([x0, y0, x0 + card_w - 1, y0 + card_h - 1], fill=(22, 27, 34), outline=(48, 54, 61), width=1)
        draw.text((x0 + 12, y0 + 8), title, fill=(240, 246, 252), font=font)

        disp709 = gtc.dwg_di_to_rec709_display(np.clip(di_arr, 0.0, 1.0))
        u8_img = Image.fromarray(np.round(np.clip(disp709, 0.0, 1.0) * 255.0).astype(np.uint8), mode="RGB")
        resized = u8_img.resize((tile_w, tile_h), Image.Resampling.LANCZOS)
        canvas.paste(resized, (x0 + 1, y0 + 1 + hdr_h))

    out_path = ASSETS_DIR / "comparison_rec709.png"
    canvas.save(out_path, optimize=True)
    print(f"Generated comparison preview: {out_path} ({canvas_w}x{canvas_h})")


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    generate_banner_svg()
    generate_rolloff_svg()
    generate_warm_skin_svg()
    generate_comparison_png()
    print("All assets regenerated cleanly.")


if __name__ == "__main__":
    main()
