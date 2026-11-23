"""
Automated mathematical & 3D LUT accuracy verification for DWG_Shadow_Desat.dctl.
Simulates float32 GPU execution 1:1 with the DCTL source code.
"""

import numpy as np

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


def di_to_linear(y: np.ndarray) -> np.ndarray:
    y = y.astype(np.float32)
    return np.where(
        y <= DI_LOG_CUT,
        y / DI_M,
        np.exp2((y / DI_C) - DI_B) - DI_A,
    ).astype(np.float32)


def linear_to_di(x: np.ndarray) -> np.ndarray:
    x = x.astype(np.float32)
    safe_x = np.maximum(x, np.float32(-DI_A + 1e-7))
    return np.where(
        x <= DI_LIN_CUT,
        x * DI_M,
        (np.log2(safe_x + DI_A) + DI_B) * DI_C,
    ).astype(np.float32)


def smax_c2(a: np.ndarray, b: np.ndarray, k: np.ndarray) -> np.ndarray:
    k_safe = np.maximum(k, np.float32(1e-8))
    h = np.maximum(k_safe - np.abs(a - b), np.float32(0.0)) / k_safe
    res = np.maximum(a, b) + h * h * h * k_safe * np.float32(1.0 / 6.0)
    return np.where(k <= np.float32(1e-8), np.maximum(a, b), res).astype(np.float32)


def smooth3(t: np.ndarray) -> np.ndarray:
    x = np.clip(t, np.float32(0.0), np.float32(1.0))
    return (x * x * (np.float32(3.0) - np.float32(2.0) * x)).astype(np.float32)


def smooth5(t: np.ndarray) -> np.ndarray:
    x = np.clip(t, np.float32(0.0), np.float32(1.0))
    return (x * x * x * (x * (x * np.float32(6.0) - np.float32(15.0)) + np.float32(10.0))).astype(np.float32)


def smoothstep_c2(edge0: float, edge1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - np.float32(edge0)) / np.float32(edge1 - edge0), np.float32(0.0), np.float32(1.0))
    return smooth5(t)


def cbrtf_safe(x: np.ndarray) -> np.ndarray:
    return np.where(
        x == np.float32(0.0),
        np.float32(0.0),
        np.copysign(np.power(np.abs(x), np.float32(1.0 / 3.0)), x),
    ).astype(np.float32)


M_DWG_TO_LMS = np.array(
    [
        [0.68578439, 0.45579386, -0.14157825],
        [0.27426684, 0.81177760, -0.08604444],
        [0.04348923, 0.15065235, 0.80585842],
    ],
    dtype=np.float32,
)

M_LMS_TO_DWG = np.array(
    [
        [1.88341962, -1.09716253, 0.21374291],
        [-0.63453134, 1.57756719, 0.05696415],
        [0.01698210, -0.23571070, 1.21872859],
    ],
    dtype=np.float32,
)

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
        [1.00000001, -0.10556134, -0.06385417],
        [1.00000005, -0.08948418, -1.29148554],
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
    r, g, b = lin[:, 0], lin[:, 1], lin[:, 2]

    # 1. Safe-Y
    y_cie = (
        np.float32(0.27411851) * r
        + np.float32(0.87363190) * g
        - np.float32(0.14775041) * b
    )
    rgb_pos = np.maximum(lin, np.float32(0.0))
    y_pos_floor = np.float32(0.03) * (
        np.float32(0.25) * rgb_pos[:, 0]
        + np.float32(0.60) * rgb_pos[:, 1]
        + np.float32(0.15) * rgb_pos[:, 2]
    )
    k_smooth = np.float32(0.03) * (rgb_pos[:, 0] + rgb_pos[:, 1] + rgb_pos[:, 2])
    y_safe = np.maximum(smax_c2(y_cie, y_pos_floor, k_smooth), np.float32(0.0))

    # 2. OkLab + imaginary gamut safety
    lms = lin @ M_DWG_TO_LMS.T
    min_lms = np.min(lms, axis=-1)
    max_lms = np.max(lms, axis=-1)
    lms_ratio = min_lms / np.maximum(max_lms, np.float32(1e-7))
    oklab_valid = smoothstep_c2(-0.02, 0.04, lms_ratio)

    lms_cbrt = cbrtf_safe(lms)
    lab = lms_cbrt @ M_LMS_TO_LAB.T

    # 3. Shadow weight (dynamic 33-pt LUT span protection + smooth3)
    luma_di = linear_to_di(y_safe)
    min_span = np.minimum(np.float32(0.085) * np.maximum(np.float32(rolloff_curve), np.float32(1.0)), np.float32(0.14))
    pivot_val = np.maximum(np.float32(shadow_pivot), min_span)
    floor_val = np.maximum(np.minimum(np.float32(black_floor), pivot_val - min_span), np.float32(0.0))

    t = np.clip((pivot_val - luma_di) / (pivot_val - floor_val), np.float32(0.0), np.float32(1.0))
    t_shaped = np.where(t > np.float32(0.0), np.power(t, np.float32(rolloff_curve)), np.float32(0.0))
    w_shadow = smooth3(t_shaped)

    # 4. Warm / Skin protect (Lorentzian chroma-regularized raised-cosine bell, sigma_c = 0.018)
    cos48 = np.float32(0.66913061)
    sin48 = np.float32(0.74314483)
    c_sq = lab[:, 1] * lab[:, 1] + lab[:, 2] * lab[:, 2]
    c_lab = np.sqrt(c_sq)
    p_warm = np.maximum(lab[:, 1] * cos48 + lab[:, 2] * sin48, np.float32(0.0))
    warm_w = (p_warm * p_warm) / (c_sq + np.float32(0.000324))

    w_eff = w_shadow * (np.float32(1.0) - np.float32(warm_protect) * warm_w)
    desat_amount = np.float32(desat_strength) * w_eff

    # 5. Dual engines
    gray_lin = np.repeat(y_safe[:, None], 3, axis=1)
    out_lin_linear = lin + (gray_lin - lin) * desat_amount[:, None]

    if desat_engine == ENGINE_OKLAB:
        sat_scale = np.float32(1.0) - desat_amount
        lab_desat = np.stack([lab[:, 0], lab[:, 1] * sat_scale, lab[:, 2] * sat_scale], axis=-1)
        lms_cbrt_desat = lab_desat @ M_LAB_TO_LMS.T
        lms_desat = lms_cbrt_desat * lms_cbrt_desat * lms_cbrt_desat
        out_lin_oklab = lms_desat @ M_LMS_TO_DWG.T
        out_lin = out_lin_linear + (out_lin_oklab - out_lin_linear) * oklab_valid[:, None]
    else:
        out_lin = out_lin_linear

    # 6. Chroma-coupled density
    rel_chroma_oklab = np.where(lab[:, 0] > np.float32(1e-5), c_lab / np.maximum(lab[:, 0], np.float32(1e-5)), np.float32(0.0))
    diff_lin = lin - gray_lin
    rel_chroma_lin = np.sqrt(np.sum(diff_lin * diff_lin, axis=-1)) / (y_safe + np.float32(1e-5))
    rc = rel_chroma_lin + (rel_chroma_oklab - rel_chroma_lin) * oklab_valid
    chroma_factor = rc / (rc + np.float32(0.25))
    density_gain = np.exp2(np.float32(chroma_density) * chroma_factor * desat_amount * np.float32(2.0))
    out_lin = out_lin * density_gain[:, None]

    # 7. Encode to DI (exact bypass when desat_amount <= 0)
    out_di = np.where(desat_amount[:, None] <= np.float32(0.0), pts, linear_to_di(out_lin))

    if preview_mode == PREVIEW_HIGHLIGHT:
        highlight_bg = np.float32(0.336043)
        out_di = highlight_bg + (out_di - highlight_bg) * w_eff[:, None]
    elif preview_mode == PREVIEW_MASK:
        out_di = np.repeat(desat_amount[:, None], 3, axis=1)
    elif preview_mode == PREVIEW_DELTA:
        out_di = np.float32(4.0) * np.abs(out_di - pts)

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
    lin_r = di_to_linear(rand_pts)
    y_cie = 0.27411851 * lin_r[:, 0] + 0.87363190 * lin_r[:, 1] - 0.14775041 * lin_r[:, 2]
    rgb_pos = np.maximum(lin_r, 0.0)
    y_floor = 0.03 * (0.25 * rgb_pos[:, 0] + 0.60 * rgb_pos[:, 1] + 0.15 * rgb_pos[:, 2])
    k = 0.03 * np.sum(rgb_pos, axis=-1)
    y_safe = np.maximum(smax_c2(y_cie.astype(np.float32), y_floor.astype(np.float32), k.astype(np.float32)), 0.0)
    luma_di = linear_to_di(y_safe)

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
    # Evaluate on 10,000 realistic camera/image colors (-10 EV to +2 EV around 18% gray, Rec.709 -> DWG/DI)
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
            dict(rms33=0.0005, max33=0.005, rms65=0.0002, max65=0.002),
        ),
        (
            "Steep Noise OkLab (pivot=0.16, floor=0.06, curve=1.8)",
            dict(desat_engine=ENGINE_OKLAB, desat_strength=1.0, shadow_pivot=0.16, black_floor=0.06, rolloff_curve=1.8, chroma_density=-0.15),
            dict(rms33=0.0008, max33=0.010, rms65=0.0003, max65=0.0025),
        ),
        (
            "Default Linear (pivot=0.28, floor=0.08, curve=1.0)",
            dict(desat_engine=ENGINE_LINEAR, desat_strength=0.85, shadow_pivot=0.28, black_floor=0.08, rolloff_curve=1.0, chroma_density=-0.08),
            dict(rms33=0.0005, max33=0.005, rms65=0.0002, max65=0.002),
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
    # 8a. Unselected midtones/highlights (luma_di >= pivot) must output exact 18% DI gray [0.336043]
    mid_hl_pts = np.array([[0.35, 0.40, 0.45], [0.55, 0.60, 0.70], [0.85, 0.85, 0.85]], dtype=np.float32)
    hl_mid_out = dctl_transform(mid_hl_pts, preview_mode=PREVIEW_HIGHLIGHT, shadow_pivot=0.28, black_floor=0.08)
    assert np.max(np.abs(hl_mid_out - hl_bg)) < 1e-6, f"Unselected region did not turn to 18% gray: {hl_mid_out}"

    # 8b. Deep shadow (luma_di <= floor -> w_eff == 1) must match normal processed out_di
    deep_pts = np.array([[0.02, 0.05, 0.03], [0.04, 0.04, 0.07], [0.00, 0.00, 0.00]], dtype=np.float32)
    hl_deep_out = dctl_transform(deep_pts, preview_mode=PREVIEW_HIGHLIGHT, shadow_pivot=0.28, black_floor=0.08, desat_strength=0.85)
    norm_deep_out = dctl_transform(deep_pts, preview_mode=PREVIEW_OFF, shadow_pivot=0.28, black_floor=0.08, desat_strength=0.85)
    assert np.max(np.abs(hl_deep_out - norm_deep_out)) < 1e-6, "Full-weight shadow did not match normal output in Highlight mode!"

    # 8c. Even when desat_strength == 0.0, Highlight mode shows deep shadows as original and highlights as 18% gray
    hl_zero_deep = dctl_transform(deep_pts, preview_mode=PREVIEW_HIGHLIGHT, shadow_pivot=0.28, black_floor=0.08, desat_strength=0.0)
    hl_zero_mid = dctl_transform(mid_hl_pts, preview_mode=PREVIEW_HIGHLIGHT, shadow_pivot=0.28, black_floor=0.08, desat_strength=0.0)
    assert np.max(np.abs(hl_zero_deep - deep_pts)) < 1e-6, "Highlight mode failed on shadows when desat_strength=0!"
    assert np.max(np.abs(hl_zero_mid - hl_bg)) < 1e-6, "Highlight mode failed to isolate highlights when desat_strength=0!"

    # 8d. Full 33^3 grid in Highlight mode must be 100% finite
    lut33_hl = build_3d_lut(33, preview_mode=PREVIEW_HIGHLIGHT)
    assert np.all(np.isfinite(lut33_hl)), "Found NaN/Inf in 33^3 Highlight mode grid!"
    print("PASS: Highlight mode isolates midtones/highlights to 18% DI gray (0.336043) and renders selected shadows cleanly.")

    print("\n=== 9. Negative Sensor Floor-Noise Continuity Test ===")
    # 9a. Negative sensor noise sweep DI=(-0.02, g, -0.01) across max_lms=1e-7 crossing
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


if __name__ == "__main__":
    run_all_tests()
