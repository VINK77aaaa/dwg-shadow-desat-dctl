"""
Automated mathematical, Apple Silicon Metal compliance, and 3D LUT accuracy verification
for DWG_Shadow_Desat.dctl. Simulates float32 GPU execution 1:1 with the DCTL source code.
"""

import re
from pathlib import Path
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
DCTL_PATH = ROOT_DIR / "DWG_Shadow_Desat.dctl"

DI_A = np.float32(0.0075)
DI_B = np.float32(7.0)
DI_C = np.float32(0.07329248)
DI_M = np.float32(10.44426855)
DI_LIN_CUT = np.float32(0.00262409)
DI_LOG_CUT = np.float32(0.02740668)

ENGINE_OKLAB = 0
ENGINE_LINEAR = 1

PREVIEW_OFF = 0
PREVIEW_HIGHLIGHT = 1
PREVIEW_MASK = 2
PREVIEW_DELTA = 3


def sqrtf_safe(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    return np.where(
        x <= np.float32(0.0),
        np.float32(0.0),
        np.sqrt(np.maximum(x, np.float32(1e-30))),
    ).astype(np.float32)


def cbrtf_pos(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    return np.where(
        x <= np.float32(0.0),
        np.float32(0.0),
        np.power(np.maximum(x, np.float32(1e-20)), np.float32(1.0 / 3.0)),
    ).astype(np.float32)


def powf_pos(x: np.ndarray, exp: float) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    return np.where(
        x <= np.float32(0.0),
        np.float32(0.0),
        np.power(np.maximum(x, np.float32(1e-20)), np.float32(exp)),
    ).astype(np.float32)


def di_to_linear(y: np.ndarray) -> np.ndarray:
    y = np.asarray(y, dtype=np.float32)
    return np.where(
        y <= DI_LOG_CUT,
        y / DI_M,
        np.exp2((y / DI_C) - DI_B) - DI_A,
    ).astype(np.float32)


def linear_to_di(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    safe_arg = np.maximum(x + DI_A, np.float32(1e-12))
    return np.where(
        x <= DI_LIN_CUT,
        x * DI_M,
        (np.log2(safe_arg) + DI_B) * DI_C,
    ).astype(np.float32)


def smooth5(t: np.ndarray) -> np.ndarray:
    x = np.clip(t, np.float32(0.0), np.float32(1.0)).astype(np.float32)
    return (
        x * x * x * (x * (x * np.float32(6.0) - np.float32(15.0)) + np.float32(10.0))
    ).astype(np.float32)


# Positive-definite Blue-Inset (aB = 0.32) D65-normalized DWG <-> OkLab LMS matrices
M_SAFE_LMS = np.array(
    [
        [0.59279668, 0.39399130, 0.01321202],
        [0.23707812, 0.70170606, 0.06121582],
        [0.03759238, 0.13022491, 0.83218271],
    ],
    dtype=np.float32,
)

M_SAFE_LMS_INV = np.array(
    [
        [2.17619412, -1.23229223, 0.05609811],
        [-0.73672953, 1.86200294, -0.12527341],
        [0.01698210, -0.23571070, 1.21872859],
    ],
    dtype=np.float32,
)

Y_SAFE_VEC = np.array([0.23694990, 0.75517334, 0.00787676], dtype=np.float32)

M_LMS_TO_LAB = np.array(
    [
        [0.21045426, 0.79361779, -0.00407205],
        [1.97799850, -2.42859221, 0.45059371],
        [0.02590404, 0.78277177, -0.80867577],
    ],
    dtype=np.float32,
)

M_LAB_TO_LMS = np.array(
    [
        [1.00000000, 0.39633779, 0.21580376],
        [1.00000000, -0.10556134, -0.06385417],
        [1.00000000, -0.08948418, -1.29148554],
    ],
    dtype=np.float32,
)


def dctl_transform(
    in_di: np.ndarray,
    desat_engine: int = ENGINE_OKLAB,
    desat_strength: float = 0.85,
    shadow_pivot: float = 0.28,
    black_floor: float = 0.08,
    rolloff_curve: float = 1.0,
    chroma_density: float = -0.08,
    warm_protect: float = 0.0,
    preview_mode: int = PREVIEW_OFF,
) -> np.ndarray:
    """Vectorized float32 1:1 implementation of DWG_Shadow_Desat.dctl."""
    in_di = np.asarray(in_di, dtype=np.float32)
    orig_shape = in_di.shape
    pts = in_di.reshape(-1, 3)

    lin = di_to_linear(pts)

    strength_val = np.clip(np.float32(desat_strength), np.float32(0.0), np.float32(1.0))
    curve_val = np.clip(np.float32(rolloff_curve), np.float32(0.40), np.float32(2.20))
    warm_val = np.clip(np.float32(warm_protect), np.float32(0.0), np.float32(1.0))
    cd_val = np.clip(np.float32(chroma_density), np.float32(-0.50), np.float32(0.30))

    lin_pos = np.maximum(lin, np.float32(0.0))
    lin_neg = np.minimum(lin, np.float32(0.0))

    # 1. Strictly positive, strictly monotonic L2 perceptual mask metric
    y_mask = sqrtf_safe(
        np.float32(0.24) * lin_pos[:, 0] * lin_pos[:, 0]
        + np.float32(0.66) * lin_pos[:, 1] * lin_pos[:, 1]
        + np.float32(0.10) * lin_pos[:, 2] * lin_pos[:, 2]
    )
    luma_di = linear_to_di(y_mask)

    # 2. Shadow weight (dynamic 33-pt LUT span protection + rational C2 smooth5)
    min_span = np.minimum(np.float32(0.095) * np.maximum(curve_val, np.float32(1.0)), np.float32(0.15))
    pivot_val = np.maximum(np.float32(shadow_pivot), min_span)
    floor_val = np.maximum(np.minimum(np.float32(black_floor), pivot_val - min_span), np.float32(0.0))

    t = np.clip((pivot_val - luma_di) / (pivot_val - floor_val), np.float32(0.0), np.float32(1.0))
    t_shaped = (t / (t + curve_val * (np.float32(1.0) - t))).astype(np.float32)
    w_shadow = smooth5(t_shaped)

    # 3. Positive-definite Blue-Inset OkLab
    lms = lin_pos @ M_SAFE_LMS.T
    lms_cbrt = cbrtf_pos(lms)
    lab = lms_cbrt @ M_LMS_TO_LAB.T

    # 4. Warm / Skin protect (luma-invariant relative-chroma Lorentzian bell)
    cos48 = np.float32(0.66913061)
    sin48 = np.float32(0.74314483)
    c_sq = lab[:, 1] * lab[:, 1] + lab[:, 2] * lab[:, 2]
    p_warm = np.maximum(lab[:, 1] * cos48 + lab[:, 2] * sin48, np.float32(0.0))
    sigma_sq = np.float32(0.0030) * lab[:, 0] * lab[:, 0] + np.float32(1e-8)
    warm_w = (p_warm * p_warm) / (c_sq + sigma_sq)

    w_eff = w_shadow * (np.float32(1.0) - warm_val * warm_w)
    desat_amount = strength_val * w_eff

    # 5. Dual engines + non-negative OkLab floor + neutral sub-black convergence
    sat_scale = np.float32(1.0) - desat_amount
    y_pos = (
        Y_SAFE_VEC[0] * lin_pos[:, 0]
        + Y_SAFE_VEC[1] * lin_pos[:, 1]
        + Y_SAFE_VEC[2] * lin_pos[:, 2]
    )
    gray_lin = np.repeat(y_pos[:, None], 3, axis=1)

    if desat_engine == ENGINE_OKLAB:
        lab_desat = np.stack([lab[:, 0], lab[:, 1] * sat_scale, lab[:, 2] * sat_scale], axis=-1)
        lms_cbrt_desat = lab_desat @ M_LAB_TO_LMS.T
        lms_desat = lms_cbrt_desat * lms_cbrt_desat * lms_cbrt_desat
        out_pos = np.maximum(lms_desat @ M_SAFE_LMS_INV.T, np.float32(0.0))
    else:
        out_pos = lin_pos + (gray_lin - lin_pos) * desat_amount[:, None]

    neg_mean = ((lin_neg[:, 0] + lin_neg[:, 1] + lin_neg[:, 2]) * np.float32(1.0 / 3.0))[:, None]
    out_neg = lin_neg + (neg_mean - lin_neg) * desat_amount[:, None]
    out_lin = out_pos + out_neg

    # 6. Chroma-coupled density (evaluated only when cd_val != 0)
    if np.abs(float(cd_val)) > 1e-6:
        c_lab = sqrtf_safe(c_sq)
        rc = np.where(lab[:, 0] > np.float32(1e-5), c_lab / np.maximum(lab[:, 0], np.float32(1e-5)), np.float32(0.0))
        chroma_factor = rc / (rc + np.float32(0.25))
        cd_scale = np.float32(1.2) if float(cd_val) > 0.0 else np.float32(2.0)
        density_gain = np.exp2(cd_val * chroma_factor * desat_amount * cd_scale)
        out_lin = out_lin * density_gain[:, None]

    # 7. Encode to DI (early-out / bypass when w_shadow <= 0 or desat_amount <= 0)
    active = (w_shadow > np.float32(0.0)) & (desat_amount > np.float32(0.0))
    out_di = np.where(active[:, None], linear_to_di(out_lin), pts)

    highlight_bg = np.float32(0.336043)
    if preview_mode == PREVIEW_HIGHLIGHT:
        out_di = np.where(
            w_shadow[:, None] <= np.float32(0.0),
            highlight_bg,
            highlight_bg + (out_di - highlight_bg) * w_eff[:, None],
        )
    elif preview_mode == PREVIEW_MASK:
        mask_val = np.where(w_shadow <= np.float32(0.0), np.float32(0.0), np.clip(desat_amount, np.float32(0.0), np.float32(1.0)))
        mask_di = linear_to_di(powf_pos(mask_val, 2.4))
        out_di = np.repeat(mask_di[:, None], 3, axis=1)
    elif preview_mode == PREVIEW_DELTA:
        delta_clamped = np.clip(np.float32(4.0) * np.abs(out_di - pts), np.float32(0.0), np.float32(1.0))
        delta_di = np.where(w_shadow[:, None] <= np.float32(0.0), np.float32(0.0), linear_to_di(powf_pos(delta_clamped, 2.4)))
        out_di = delta_di

    return out_di.reshape(orig_shape)


def build_3d_lut(size: int, **kwargs) -> np.ndarray:
    axis = np.linspace(0.0, 1.0, size, dtype=np.float32)
    r, g, b = np.meshgrid(axis, axis, axis, indexing="ij")
    grid = np.stack([r, g, b], axis=-1)
    return dctl_transform(grid, **kwargs)


def eval_tetrahedral_lut(lut: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Standard tetrahedral 3D LUT interpolation on [0, 1]^3."""
    size = lut.shape[0]
    scaled = np.clip(pts, 0.0, 1.0) * (size - 1)
    idx0 = np.floor(scaled).astype(np.int32)
    idx0 = np.minimum(idx0, size - 2)
    f = scaled - idx0
    fx, fy, fz = f[:, 0:1], f[:, 1:2], f[:, 2:3]

    i0, j0, k0 = idx0[:, 0], idx0[:, 1], idx0[:, 2]
    i1, j1, k1 = i0 + 1, j0 + 1, k0 + 1

    c000 = lut[i0, j0, k0]
    c100 = lut[i1, j0, k0]
    c010 = lut[i0, j1, k0]
    c001 = lut[i0, j0, k1]
    c110 = lut[i1, j1, k0]
    c101 = lut[i1, j0, k1]
    c011 = lut[i0, j1, k1]
    c111 = lut[i1, j1, k1]

    out = np.empty_like(c000)

    fx_1d, fy_1d, fz_1d = fx[:, 0], fy[:, 0], fz[:, 0]
    m1 = (fx_1d >= fy_1d) & (fy_1d >= fz_1d)
    out[m1] = (c000 + fx * (c100 - c000) + fy * (c110 - c100) + fz * (c111 - c110))[m1]

    m2 = (fx_1d >= fz_1d) & (fz_1d > fy_1d)
    out[m2] = (c000 + fx * (c100 - c000) + fz * (c101 - c100) + fy * (c111 - c101))[m2]

    m3 = (fz_1d > fx_1d) & (fx_1d >= fy_1d)
    out[m3] = (c000 + fz * (c001 - c000) + fx * (c101 - c001) + fy * (c111 - c101))[m3]

    m4 = (fy_1d > fx_1d) & (fx_1d >= fz_1d)
    out[m4] = (c000 + fy * (c010 - c000) + fx * (c110 - c010) + fz * (c111 - c110))[m4]

    m5 = (fy_1d >= fz_1d) & (fz_1d > fx_1d)
    out[m5] = (c000 + fy * (c010 - c000) + fz * (c011 - c010) + fx * (c111 - c011))[m5]

    m6 = ~(m1 | m2 | m3 | m4 | m5)
    out[m6] = (c000 + fz * (c001 - c000) + fy * (c011 - c001) + fx * (c111 - c011))[m6]

    return out


def rec709_to_dwg_di(rgb709_gamma24: np.ndarray) -> np.ndarray:
    lin709 = np.power(np.clip(rgb709_gamma24, 0.0, 1.0), 2.4)
    m_709_to_dwg = np.array(
        [
            [0.562767, 0.323517, 0.113716],
            [0.077755, 0.749577, 0.172668],
            [0.064669, 0.191999, 0.743332],
        ],
        dtype=np.float32,
    )
    dwg_lin = lin709.astype(np.float32) @ m_709_to_dwg.T
    return linear_to_di(dwg_lin)


def _extract_dctl_matrix(source: str, func_name: str) -> np.ndarray:
    m = re.search(rf"__DEVICE__\s+float3\s+{func_name}\s*\([^)]*\)\s*\{{(.*?)\}}", source, re.S)
    assert m is not None, f"Could not find {func_name} in {DCTL_PATH.name}"
    pairs = re.findall(r"([-+]?)\s*(\d+\.\d+)[fF]", m.group(1))
    assert len(pairs) == 9, f"Expected 9 matrix weights in {func_name}, got {len(pairs)}"
    nums = [float(f"{sign}{num}") for sign, num in pairs]
    return np.array(nums, dtype=np.float32).reshape(3, 3)


def run_all_tests():
    print("=== 1. Boundary & NaN/Inf Safety Test (33^3 grid + negative inputs) ===")
    lut33 = build_3d_lut(33)
    assert np.all(np.isfinite(lut33)), "Found NaN/Inf in 33^3 LUT!"
    neg_pts = np.array(
        [[-0.01, -0.01, -0.01], [0.0, 0.0, 0.0], [-0.005, 0.1, -0.002], [0.0, 0.0, 0.15]],
        dtype=np.float32,
    )
    neg_out = dctl_transform(neg_pts)
    assert np.all(np.isfinite(neg_out)), "Found NaN/Inf on negative/zero inputs!"
    print("PASS: 33^3 grid and negative corner inputs are 100% finite.")

    print("\n=== 2. Pure Black & Neutral Gray Strict Invariance Test ===")
    grays = np.repeat(np.linspace(0.0, 1.0, 1001, dtype=np.float32)[:, None], 3, axis=1)
    extreme_configs = [
        dict(desat_engine=ENGINE_OKLAB, desat_strength=1.0, shadow_pivot=0.60, black_floor=0.35, chroma_density=-0.50, warm_protect=1.0),
        dict(desat_engine=ENGINE_OKLAB, desat_strength=1.0, shadow_pivot=0.60, black_floor=0.00, chroma_density=0.30, warm_protect=0.0),
        dict(desat_engine=ENGINE_LINEAR, desat_strength=1.0, shadow_pivot=0.60, black_floor=0.10, chroma_density=-0.50, warm_protect=1.0),
    ]
    for idx, cfg in enumerate(extreme_configs):
        out_g = dctl_transform(grays, **cfg)
        err = np.max(np.abs(out_g - grays))
        print(f"  Config {idx+1} max neutral gray deviation: {err:.2e}")
        assert err < 1e-6, f"Neutral gray drifted by {err}!"
    assert np.max(np.abs(dctl_transform([[0.0, 0.0, 0.0]])[0])) == 0.0
    print("PASS: Pure black = (0,0,0) and all neutral grays invariant (< 1e-6).")

    print("\n=== 3. Midtone & Highlight Zero-Impact Test (luma_di >= shadow_pivot) ===")
    rng = np.random.default_rng(42)
    rand_pts = rng.uniform(0.05, 0.95, size=(5000, 3)).astype(np.float32)
    lin_pos_r = np.maximum(di_to_linear(rand_pts), np.float32(0.0))
    y_mask_r = sqrtf_safe(
        np.float32(0.24) * lin_pos_r[:, 0] ** 2
        + np.float32(0.66) * lin_pos_r[:, 1] ** 2
        + np.float32(0.10) * lin_pos_r[:, 2] ** 2
    )
    luma_di = linear_to_di(y_mask_r)

    pivot = 0.28
    above_mask = luma_di >= pivot
    out_above = dctl_transform(rand_pts[above_mask], shadow_pivot=pivot, desat_strength=1.0, chroma_density=-0.50)
    err_above = np.max(np.abs(out_above - rand_pts[above_mask]))
    print(f"  Samples above pivot ({np.sum(above_mask)} pts) max deviation: {err_above:.2e}")
    assert err_above < 1e-6, f"Pixels above pivot were modified by {err_above}!"
    print("PASS: Midtones and highlights are 100% untouched.")

    print("\n=== 4. DWG Blue Negative-Weight Black-Hole Fix Test ===")
    dwg_pure_blue_noise = np.array([[0.0, 0.0, 0.15]], dtype=np.float32)
    rec709_dark_blue_di = rec709_to_dwg_di(np.array([[0.02, 0.02, 0.25]], dtype=np.float32))
    for label, sample in [("DWG Imaginary Blue Noise (0,0,0.15)", dwg_pure_blue_noise), ("Rec.709 Dark Blue in DI", rec709_dark_blue_di)]:
        for eng_name, eng in [("OkLab", ENGINE_OKLAB), ("Linear", ENGINE_LINEAR)]:
            res = dctl_transform(sample, desat_engine=eng, desat_strength=1.0, shadow_pivot=0.35, black_floor=0.15, chroma_density=0.0)
            print(f"  {label} [{eng_name}] -> DI: {np.round(res[0], 5)}")
            assert np.all(res[0] > 0.0005), f"Black hole collapse detected: {res[0]}"
            assert np.all(np.isfinite(res[0])), "Non-finite output!"
    print("PASS: No black-hole collapse or negative clipping on extreme DWG blue.")

    print("\n=== 5. Green Chroma-Noise Suppression (Preventing White Specks) Test ===")
    green_noise = np.array([[0.04, 0.14, 0.04]], dtype=np.float32)
    out_g_zero = dctl_transform(green_noise, desat_strength=1.0, shadow_pivot=0.28, black_floor=0.08, chroma_density=0.0)
    out_g_neg = dctl_transform(green_noise, desat_strength=1.0, shadow_pivot=0.28, black_floor=0.08, chroma_density=-0.20)
    print(f"  Green noise DI (0.04,0.14,0.04) -> chroma_density=0.0 : {np.round(out_g_zero[0], 5)}")
    print(f"  Green noise DI (0.04,0.14,0.04) -> chroma_density=-0.2: {np.round(out_g_neg[0], 5)}")
    assert np.mean(out_g_neg) < np.mean(out_g_zero), "Negative chroma_density did not sink chroma noise!"
    print("PASS: Negative Chroma Density sinks green noise into shadows while grays stay untouched.")

    print("\n=== 6. Warm / Skin Protection Test ===")
    dark_skin_di = rec709_to_dwg_di(np.array([[0.22, 0.14, 0.10]], dtype=np.float32))
    blue_noise_di = rec709_to_dwg_di(np.array([[0.08, 0.10, 0.24]], dtype=np.float32))
    skin_noprot = dctl_transform(dark_skin_di, warm_protect=0.0, desat_strength=0.90, shadow_pivot=0.35, black_floor=0.10, chroma_density=0.0)
    skin_prot = dctl_transform(dark_skin_di, warm_protect=0.85, desat_strength=0.90, shadow_pivot=0.35, black_floor=0.10, chroma_density=0.0)
    blue_prot = dctl_transform(blue_noise_di, warm_protect=0.85, desat_strength=0.90, shadow_pivot=0.35, black_floor=0.10, chroma_density=0.0)

    skin_chroma_orig = np.max(dark_skin_di) - np.min(dark_skin_di)
    skin_chroma_noprot = np.max(skin_noprot) - np.min(skin_noprot)
    skin_chroma_prot = np.max(skin_prot) - np.min(skin_prot)
    blue_chroma_orig = np.max(blue_noise_di) - np.min(blue_noise_di)
    blue_chroma_prot = np.max(blue_prot) - np.min(blue_prot)

    print(f"  Dark Skin DI span: orig={skin_chroma_orig:.4f}, no_protect={skin_chroma_noprot:.4f}, warm_protect(0.85)={skin_chroma_prot:.4f}")
    print(f"  Blue Noise DI span: orig={blue_chroma_orig:.4f}, warm_protect(0.85)={blue_chroma_prot:.4f}")
    assert skin_chroma_prot > skin_chroma_noprot * 2.0, "Warm protect did not preserve dark skin!"
    assert blue_chroma_prot < blue_chroma_orig * 0.35, "Warm protect weakened blue noise suppression!"
    print("PASS: Warm/Skin tones preserved while cool shadow noise is strongly desaturated.")

    print("\n=== 7. 33-pt & 65-pt 3D LUT Tetrahedral Interpolation Accuracy Test ===")
    rng_lut = np.random.default_rng(123)
    ev = rng_lut.uniform(-10.0, 2.0, size=(10000, 1))
    chrom = rng_lut.uniform(0.05, 1.0, size=(10000, 3))
    lin709 = 0.18 * np.power(2.0, ev) * chrom / np.mean(chrom, axis=1, keepdims=True)
    m_709_to_dwg = np.array(
        [
            [0.562767, 0.323517, 0.113716],
            [0.077755, 0.749577, 0.172668],
            [0.064669, 0.191999, 0.743332],
        ],
        dtype=np.float32,
    )
    pts_real_gamut = np.clip(linear_to_di(lin709.astype(np.float32) @ m_709_to_dwg.T), 0.0, 1.0)

    lut_configs = [
        (
            "Default OkLab (pivot=0.28, floor=0.08, curve=1.0)",
            dict(desat_engine=ENGINE_OKLAB, desat_strength=0.85, shadow_pivot=0.28, black_floor=0.08, rolloff_curve=1.0, chroma_density=-0.08),
            dict(rms33=0.0003, max33=0.0015, rms65=0.0001, max65=0.0006),
        ),
        (
            "Steep Noise OkLab (pivot=0.16, floor=0.06, curve=1.8)",
            dict(desat_engine=ENGINE_OKLAB, desat_strength=1.0, shadow_pivot=0.16, black_floor=0.06, rolloff_curve=1.8, chroma_density=-0.15),
            dict(rms33=0.0005, max33=0.0030, rms65=0.0002, max65=0.0010),
        ),
        (
            "Default Linear (pivot=0.28, floor=0.08, curve=1.0)",
            dict(desat_engine=ENGINE_LINEAR, desat_strength=0.85, shadow_pivot=0.28, black_floor=0.08, rolloff_curve=1.0, chroma_density=-0.08),
            dict(rms33=0.0003, max33=0.0015, rms65=0.0001, max65=0.0006),
        ),
    ]
    for name, cfg, bounds in lut_configs:
        lut33_c = build_3d_lut(33, **cfg)
        lut65_c = build_3d_lut(65, **cfg)
        ref = dctl_transform(pts_real_gamut, **cfg)
        interp33 = eval_tetrahedral_lut(lut33_c, pts_real_gamut)
        interp65 = eval_tetrahedral_lut(lut65_c, pts_real_gamut)

        diff33 = np.abs(interp33 - ref)
        diff65 = np.abs(interp65 - ref)
        rms33 = float(np.sqrt(np.mean(diff33 * diff33)))
        max33 = float(np.max(diff33))
        rms65 = float(np.sqrt(np.mean(diff65 * diff65)))
        max65 = float(np.max(diff65))
        print(f"  [{name}]")
        print(f"    33-pt LUT: RMS={rms33:.6f} (<{bounds['rms33']}), Max={max33:.6f} (<{bounds['max33']})")
        print(f"    65-pt LUT: RMS={rms65:.6f} (<{bounds['rms65']}), Max={max65:.6f} (<{bounds['max65']})")
        assert rms33 < bounds["rms33"], f"33-pt LUT RMS too high: {rms33}"
        assert max33 < bounds["max33"], f"33-pt LUT Max error too high: {max33}"
        assert rms65 < bounds["rms65"], f"65-pt LUT RMS too high: {rms65}"
        assert max65 < bounds["max65"], f"65-pt LUT Max error too high: {max65}"
    print("PASS: All 33-pt and 65-pt 3D LUT interpolation checks meet high-precision targets.")

    print("\n=== 8. Highlight Mode Test ===")
    hl_bg = np.float32(0.336043)
    mid_hl_pts = np.array([[0.35, 0.40, 0.45], [0.55, 0.60, 0.70], [0.85, 0.85, 0.85]], dtype=np.float32)
    hl_mid_out = dctl_transform(mid_hl_pts, preview_mode=PREVIEW_HIGHLIGHT, shadow_pivot=0.28, black_floor=0.08)
    assert np.max(np.abs(hl_mid_out - hl_bg)) < 1e-6, f"Unselected region did not turn to 18% gray: {hl_mid_out}"

    deep_pts = np.array([[0.02, 0.05, 0.03], [0.04, 0.04, 0.07], [0.00, 0.00, 0.00]], dtype=np.float32)
    hl_deep_out = dctl_transform(deep_pts, preview_mode=PREVIEW_HIGHLIGHT, shadow_pivot=0.28, black_floor=0.08, desat_strength=0.85)
    norm_deep_out = dctl_transform(deep_pts, preview_mode=PREVIEW_OFF, shadow_pivot=0.28, black_floor=0.08, desat_strength=0.85)
    assert np.max(np.abs(hl_deep_out - norm_deep_out)) < 1e-6, "Full-weight shadow did not match normal output in Highlight mode!"

    hl_zero_deep = dctl_transform(deep_pts, preview_mode=PREVIEW_HIGHLIGHT, shadow_pivot=0.28, black_floor=0.08, desat_strength=0.0)
    hl_zero_mid = dctl_transform(mid_hl_pts, preview_mode=PREVIEW_HIGHLIGHT, shadow_pivot=0.28, black_floor=0.08, desat_strength=0.0)
    assert np.max(np.abs(hl_zero_deep - deep_pts)) < 1e-6, "Highlight mode failed on shadows when desat_strength=0!"
    assert np.max(np.abs(hl_zero_mid - hl_bg)) < 1e-6, "Highlight mode failed to isolate highlights when desat_strength=0!"

    lut33_hl = build_3d_lut(33, preview_mode=PREVIEW_HIGHLIGHT)
    assert np.all(np.isfinite(lut33_hl)), "Found NaN/Inf in 33^3 Highlight mode grid!"
    print("PASS: Highlight mode isolates midtones/highlights to 18% DI gray (0.336043) and renders selected shadows cleanly.")

    print("\n=== 9. Negative Sensor Floor-Noise Continuity Test ===")
    # 9a. Negative sensor noise sweep DI=(-0.02, g, -0.01) across the zero-crossing of green
    g_vals = np.linspace(0.0054, 0.0057, 7, dtype=np.float32)
    pts_neg_g = np.zeros((len(g_vals), 3), dtype=np.float32)
    pts_neg_g[:, 0] = -0.02
    pts_neg_g[:, 1] = g_vals
    pts_neg_g[:, 2] = -0.01
    out_neg_g = dctl_transform(pts_neg_g, desat_engine=ENGINE_OKLAB, desat_strength=1.0, chroma_density=0.0)
    assert np.all(np.isfinite(out_neg_g)), "Non-finite output in negative floor-noise sweep!"
    diffs_g = np.diff(out_neg_g, axis=0)
    max_step_g = float(np.max(np.abs(diffs_g)))
    assert np.all(diffs_g >= -1e-7), f"Negative floor-noise sweep not monotonic: {diffs_g}"
    assert max_step_g < 1e-4, f"Step discontinuity detected in negative floor-noise sweep: {max_step_g}"

    # 9b. Near-zero blue channel sweep DI=(0, 0, b) from 0 to 5e-6
    b_vals = np.array([0.0, 0.5e-6, 1.0e-6, 1.2e-6, 1.3e-6, 1.5e-6, 2.0e-6, 5.0e-6], dtype=np.float32)
    pts_near_b = np.zeros((len(b_vals), 3), dtype=np.float32)
    pts_near_b[:, 2] = b_vals
    out_near_b = dctl_transform(pts_near_b, desat_engine=ENGINE_OKLAB, desat_strength=1.0, chroma_density=0.0)
    assert np.all(np.isfinite(out_near_b)), "Non-finite output in near-zero blue sweep!"
    diffs_b = np.diff(out_near_b, axis=0)
    max_step_b = float(np.max(np.abs(diffs_b)))
    assert np.all(diffs_b >= -1e-9), f"Near-zero blue sweep not monotonic: {diffs_b}"
    assert max_step_b < 1e-4, f"Step discontinuity detected in near-zero blue sweep: {max_step_b}"
    print(f"PASS: Negative floor-noise sweep (max_step={max_step_g:.2e}) and near-zero blue sweep (max_step={max_step_b:.2e}) are strictly monotonic and continuous.")

    print("\n=== 10. High-Sat Blue/Violet Monotonicity & Full 33^3 S-Log3 Pipeline Stress Test ===")
    b_seq = np.linspace(0.30, 0.70, 21, dtype=np.float32)
    pts_sw = np.column_stack([np.full(21, 0.33), np.full(21, 0.25), b_seq]).astype(np.float32)
    for piv in [0.28, 0.55]:
        out_sw = dctl_transform(pts_sw, shadow_pivot=piv, desat_strength=0.85, chroma_density=-0.08)
        db_ch = np.diff(out_sw[:, 2])
        print(f"  Killer blue sweep (Pivot={piv:.2f}): min dB={db_ch.min():+.6f}")
        assert db_ch.min() >= -1e-6, f"Non-monotonic B collapse at Pivot={piv}: {db_ch}"

    ax33 = np.linspace(0.0, 1.0, 33, dtype=np.float32)
    rr, gg, bb = np.meshgrid(ax33, ax33, ax33, indexing="ij")
    sl3_grid = np.stack([rr, gg, bb], axis=-1).reshape(-1, 3)
    lin_sl3 = np.where(
        sl3_grid >= np.float32(171.2102946929 / 1023.0),
        np.power(np.float32(10.0), (sl3_grid * np.float32(1023.0) - np.float32(420.0)) / np.float32(261.5)) * np.float32(0.19) - np.float32(0.01),
        (sl3_grid * np.float32(1023.0) - np.float32(95.0)) * np.float32(0.01125 / (171.2102946929 - 95.0)),
    ).astype(np.float32)
    m_sg3c_to_xyz = np.array(
        [
            [0.5990839208, 0.2489255161, 0.1024464903],
            [0.2150758201, 0.8850685017, -0.1001443219],
            [-0.0320658495, -0.0276583907, 1.1487819910],
        ],
        dtype=np.float32,
    )
    m_xyz_to_dwg = np.array(
        [
            [1.51667204, -0.28147805, -0.14696363],
            [-0.46491710, 1.25142378, 0.17488461],
            [0.06484905, 0.10913934, 0.76141462],
        ],
        dtype=np.float32,
    )
    di_in_sl3 = linear_to_di(lin_sl3 @ (m_xyz_to_dwg @ m_sg3c_to_xyz).T)
    di_graded = (di_in_sl3 - np.float32(0.336)) * np.float32(1.25) + np.float32(0.336)
    low_w = np.clip((np.float32(0.30) - di_graded[:, 0]) / np.float32(0.30), np.float32(0.0), np.float32(1.0)) ** 2
    di_graded[:, 0] -= np.float32(0.188) * low_w * np.float32(0.35)

    for tag, cfg in [
        ("Default OkLab (Pivot=0.28)", dict(desat_engine=ENGINE_OKLAB, desat_strength=0.85, shadow_pivot=0.28, black_floor=0.08, chroma_density=-0.08)),
        ("Extreme OkLab (Pivot=0.55)", dict(desat_engine=ENGINE_OKLAB, desat_strength=1.00, shadow_pivot=0.55, black_floor=0.08, chroma_density=-0.20)),
        ("Extreme Linear (Pivot=0.55)", dict(desat_engine=ENGINE_LINEAR, desat_strength=1.00, shadow_pivot=0.55, black_floor=0.08, chroma_density=-0.20)),
    ]:
        c_out = dctl_transform(di_graded, **cfg).reshape(33, 33, 33, 3)
        inv_r = int(np.sum((c_out[1:, :, :, 0] - c_out[:-1, :, :, 0]) < -0.01))
        inv_g = int(np.sum((c_out[:, 1:, :, 1] - c_out[:, :-1, :, 1]) < -0.01))
        inv_b = int(np.sum((c_out[:, :, 1:, 2] - c_out[:, :, :-1, 2]) < -0.01))
        print(f"  33^3 S-Log3 [{tag}]: main-channel inversions (<-0.01) R={inv_r}, G={inv_g}, B={inv_b}")
        assert inv_r == 0 and inv_g == 0 and inv_b == 0, f"Channel inversions detected in {tag}: {(inv_r, inv_g, inv_b)}"
    print("PASS: High-saturation blue/violet sweep and full 33^3 S-Log3 graded pipeline have 0 channel inversions.")

    print("\n=== 11. DCTL Source Static Compliance, Apple Silicon Metal Safety & Constant Sync ===")
    raw_bytes = DCTL_PATH.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "DCTL file must not have UTF-8 BOM!"
    assert b"\r\n" not in raw_bytes, "DCTL file must use LF line endings, found CRLF!"
    assert all(b < 128 for b in raw_bytes), "DCTL file must be pure ASCII for cross-platform Metal safety!"
    src_text = raw_bytes.decode("ascii")

    forbidden = ["_cbrtf", "_fabsf", "isnan", "isfinite", "__DEVICE__ inline", "smoothstep("]
    for sym in forbidden:
        assert sym not in src_text, f"Forbidden Metal/DCTL symbol found in source: {sym}"

    for lineno, line in enumerate(src_text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("DEFINE_UI_PARAMS"):
            assert not stripped.endswith(";"), f"DEFINE_UI_PARAMS line {lineno} must not end with semicolon!"
            continue
        if not stripped or stripped.startswith("//"):
            continue
        code_only = stripped.split("//")[0]
        for m in re.finditer(r"(?<![A-Za-z0-9_.])(?:\d+\.\d*|\.\d+|\d+[eE][+-]?\d+)(?:[eE][+-]?\d+)?[A-Za-z_]*", code_only):
            tok = m.group(0)
            assert tok.endswith("f") or tok.endswith("F"), f"Float literal missing 'f' suffix on line {lineno}: {tok}"

    di_macros = {
        "DI_A": DI_A,
        "DI_B": DI_B,
        "DI_C": DI_C,
        "DI_M": DI_M,
        "DI_LIN_CUT": DI_LIN_CUT,
        "DI_LOG_CUT": DI_LOG_CUT,
    }
    for macro, py_val in di_macros.items():
        mm = re.search(rf"#define\s+{macro}\s+([-+]?\d+\.\d+)[fF]", src_text)
        assert mm is not None, f"Missing macro {macro} in DCTL!"
        assert np.float32(float(mm.group(1))) == py_val, f"Macro {macro} mismatch: DCTL={mm.group(1)} vs py={py_val}"

    assert np.max(np.abs(_extract_dctl_matrix(src_text, "dwg_lin_to_lms_safe") - M_SAFE_LMS)) < 1e-7
    assert np.max(np.abs(_extract_dctl_matrix(src_text, "lms_safe_to_dwg_lin") - M_SAFE_LMS_INV)) < 1e-7
    assert np.max(np.abs(_extract_dctl_matrix(src_text, "lms_cbrt_to_lab") - M_LMS_TO_LAB)) < 1e-7
    assert np.max(np.abs(_extract_dctl_matrix(src_text, "lab_to_lms_cbrt") - M_LAB_TO_LMS)) < 1e-7
    ym = re.search(r"float Y_pos = ([\d.]+)[fF] \* lin_pos\.x \+ ([\d.]+)[fF] \* lin_pos\.y \+ ([\d.]+)[fF] \* lin_pos\.z;", src_text)
    assert ym is not None, "Missing Y_pos linear luma weights in DCTL!"
    assert np.max(np.abs(np.array([float(ym.group(1)), float(ym.group(2)), float(ym.group(3))], dtype=np.float32) - Y_SAFE_VEC)) < 1e-7
    print("PASS: DCTL is LF/ASCII/no-BOM, Metal-safe, all float literals carry 'f', and all constants match 1:1.")

    print("\n=== 12. Sub-Black Neutral Gray Invariance & [0,1]^3 Non-Negative Closure ===")
    full_grays = np.repeat(np.linspace(-0.20, 1.00, 1201, dtype=np.float32)[:, None], 3, axis=1)
    for cfg in extreme_configs:
        out_fg = dctl_transform(full_grays, **cfg)
        err_fg = float(np.max(np.abs(out_fg - full_grays)))
        assert err_fg < 1e-6, f"Sub-black/full neutral gray drifted by {err_fg}!"
    for piv, flr in [(0.28, 0.08), (0.60, 0.35)]:
        g_nonneg = build_3d_lut(33, desat_engine=ENGINE_OKLAB, desat_strength=0.85, shadow_pivot=piv, black_floor=flr, chroma_density=-0.08)
        min_out = float(np.min(g_nonneg))
        assert min_out >= 0.0, f"Negative undershoot on [0,1]^3 grid (pivot={piv}): {min_out}"
    print("PASS: Neutral grays across [-0.20, 1.00] are strictly invariant (< 1e-6) and [0,1]^3 output is strictly non-negative.")

    print("\n=== 13. Full-Range Rolloff Curve C2 Endpoint Smoothness Test (0.40 ~ 2.20) ===")
    for rc in [0.40, 1.00, 2.20]:
        for label, edge in [("Shadow Pivot", 0.28), ("Black Floor", 0.08)]:
            eps = 1e-4
            xs = np.array([edge - 2 * eps, edge - eps, edge, edge + eps, edge + 2 * eps], dtype=np.float64)
            t_arr = np.clip((0.28 - xs) / (0.28 - 0.08), 0.0, 1.0)
            ts = t_arr / (t_arr + rc * (1.0 - t_arr))
            w_arr = ts ** 3 * (ts * (ts * 6.0 - 15.0) + 10.0)
            dw = np.diff(w_arr) / eps
            d2w = np.diff(dw) / eps
            assert np.max(np.abs(dw)) < 0.05, f"Slope spike at {label} for rolloff={rc}: {dw}"
            assert np.max(np.abs(d2w)) < 250.0, f"Curvature spike at {label} for rolloff={rc}: {d2w}"
    print("PASS: Rational Schlick + smooth5 maintains C2 endpoint smoothness across [0.40, 2.20].")

    print("\n=== 14. Warm Skin Cross-Exposure Scale Invariance & SDR Mask Non-Clipping Test ===")
    skin_base_709 = np.array([0.82, 0.44, 0.25], dtype=np.float64)
    y0_skin = 0.2126 * skin_base_709[0] + 0.7152 * skin_base_709[1] + 0.0722 * skin_base_709[2]
    m_709_to_dwg_64 = np.array(
        [
            [0.562767, 0.323517, 0.113716],
            [0.077755, 0.749577, 0.172668],
            [0.064669, 0.191999, 0.743332],
        ],
        dtype=np.float64,
    )
    prot_ratios = []
    for di_lvl in [0.25, 0.18, 0.12, 0.08, 0.04, 0.02]:
        y_lin = float(di_to_linear(np.array([di_lvl], dtype=np.float32))[0])
        dwg_lin = (skin_base_709 * (y_lin / y0_skin)) @ m_709_to_dwg_64.T
        skin_pt = linear_to_di(dwg_lin.astype(np.float32))[None, :]
        # Use Black Floor = 0.35, Shadow Pivot = 0.60 so w_shadow == 1.0 for all test exposures
        mask_out = dctl_transform(
            skin_pt,
            shadow_pivot=0.60,
            black_floor=0.35,
            desat_strength=1.0,
            warm_protect=1.0,
            preview_mode=PREVIEW_MASK,
        )
        # Invert SDR display curve to recover effective desat_amount = 1 - warm_w
        eff_desat = float(np.power(np.clip(di_to_linear(mask_out[0, 0]), 0.0, 1.0), 1.0 / 2.4))
        prot_ratios.append(1.0 - eff_desat)
    prot_span = max(prot_ratios) - min(prot_ratios)
    print(f"  Skin warm_w across DI=[0.02..0.25]: min={min(prot_ratios):.4f}, max={max(prot_ratios):.4f}, span={prot_span:.6f}")
    assert prot_span < 0.005, f"Warm skin protection varied too much across shadow exposures: {prot_span}"

    # Verify PREVIEW_MASK maps [0, 1] desat_amount linearly to Rec.709 G2.4 display without clipping
    # Use achromatic black-to-floor sweep with rolloff=1.0 so desat_amount varies cleanly across [0, 1]
    ramp_gray = np.repeat(np.linspace(0.05, 0.30, 101, dtype=np.float32)[:, None], 3, axis=1)
    mask_ref_off = dctl_transform(ramp_gray, desat_engine=ENGINE_LINEAR, desat_strength=1.0, shadow_pivot=0.28, black_floor=0.08, chroma_density=0.0)
    # Also compute exact mask via PREVIEW_MASK and verify [0, 1] linearity via direct desat_amount
    ramp_mask_di = dctl_transform(ramp_gray, desat_strength=1.0, shadow_pivot=0.28, black_floor=0.08, preview_mode=PREVIEW_MASK)
    disp_mask = np.power(np.clip(di_to_linear(ramp_mask_di[:, 0]), 0.0, 1.0), 1.0 / 2.4)
    # Check smooth monotonic fall from 1.0 (at floor) to 0.0 (at pivot) without plateau clipping above 0.5136
    assert abs(float(disp_mask[0]) - 1.0) < 1e-4, f"Mask at deep shadow should display as 1.0, got {disp_mask[0]}"
    assert abs(float(disp_mask[-1]) - 0.0) < 1e-6, f"Mask above pivot should display as 0.0, got {disp_mask[-1]}"
    # Verify mid-range points (e.g. DI=0.18 where t=0.5 => smooth5(0.5)=0.5) display accurately at ~0.50, not clipped at 1.0
    pt_mid = np.array([[0.18, 0.18, 0.18]], dtype=np.float32)
    mid_mask_di = dctl_transform(pt_mid, desat_strength=1.0, shadow_pivot=0.28, black_floor=0.08, preview_mode=PREVIEW_MASK)
    mid_disp = float(np.power(np.clip(di_to_linear(mid_mask_di[0, 0]), 0.0, 1.0), 1.0 / 2.4))
    assert abs(mid_disp - 0.5) < 1e-4, f"Mid-transition mask (0.5) distorted under Output CST: {mid_disp}"
    print(f"PASS: Skin protection is luma-invariant (span={prot_span:.6f}) and PREVIEW_MASK displays 0.50-> {mid_disp:.5f}, 1.00-> {disp_mask[0]:.5f} cleanly.")


if __name__ == "__main__":
    run_all_tests()
