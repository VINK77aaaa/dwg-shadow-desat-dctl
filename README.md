<div align="center">

<img src="assets/banner.svg" alt="DWG Shadow Desat DCTL Banner" width="100%" />

<br />

[![DaVinci Resolve Studio](https://img.shields.io/badge/DaVinci%20Resolve-Studio%20DCTL-2563eb?style=for-the-badge&logo=blackmagicdesign&logoColor=white)](DWG_Shadow_Desat.dctl)
[![Color Space](https://img.shields.io/badge/Color%20Space-DWG%20%2F%20DI-0284c7?style=for-the-badge)](#%EF%B8%8F-%E6%8E%A8%E8%8D%90%E8%8A%82%E7%82%B9%E6%A0%91%E4%B8%8E%E8%89%B2%E5%BD%A9%E7%AE%A1%E7%BA%BF)
[![Desat Engine](https://img.shields.io/badge/Engine-Perceptual%20OkLab%20%26%20Linear-7c3aed?style=for-the-badge)](#-%E6%A0%B8%E5%BF%83%E5%8E%9F%E7%90%86%E4%B8%8E%E5%8F%AF%E8%A7%86%E5%8C%96)
[![3D LUT Safe](https://img.shields.io/badge/3D%20LUT-33%20%26%2065--pt%20Safe-059669?style=for-the-badge)](#-%E9%85%8D%E5%90%88%E8%BE%BE%E8%8A%AC%E5%A5%87%E7%94%9F%E6%88%90-lut%E7%9A%84%E6%93%8D%E4%BD%9C%E8%A7%84%E8%8C%83)
[![Tests](https://img.shields.io/badge/Verification-10%2C000--pt%20LUT%20Verified-d97706?style=for-the-badge)](#-%E8%87%AA%E5%8A%A8%E5%8C%96%E9%AA%8C%E8%AF%81%E4%B8%8E%E6%B5%8B%E8%AF%95%E5%8D%A1)

<p align="center">
  <strong>专精于 DaVinci Wide Gamut / DaVinci Intermediate (DWG / DI) 的暗部降饱和 DCTL 插件</strong><br />
  兼顾 <strong>高 ISO 暗部彩噪压制</strong> 与 <strong>胶片暗部自然色彩衰减</strong> · 严格中性灰零漂移 · C² 平滑过渡 · 3D LUT 导出无损安全
</p>

[效果对比](#-效果对比16-bit-dwgdi-专项测试卡) ·
[原理可视化](#-核心原理与可视化) ·
[节点管线](#%EF%B8%8F-推荐节点树与色彩管线) ·
[安装指南](#-安装方法) ·
[参数详解](#%EF%B8%8F-参数详解8-个核心控件) ·
[参考预设](#-三套实用参考预设) ·
[LUT 导出规范](#-配合达芬奇生成-lut的操作规范) ·
[项目结构](#-项目文件结构)

</div>

---


针对达芬奇原生 `Lum vs Sat` 在广色域下容易出现的 **“越降越暗 / 越降越亮”**、**“蓝偏紫 / 红偏粉”**、**“黑位绿噪变白麻点”** 以及 **“33 点 3D LUT 导出断层”** 等痛点，本插件从底层色彩科学重新构建：

| 痛点维度 | 达芬奇原生 `Lum vs Sat` | `DWG_Shadow_Desat.dctl` |
| :--- | :--- | :--- |
| 🎯 **暗部色相稳定性 (Abney 效应)** | 线性或传统圆柱饱和度收缩时，蓝色易偏紫、红色易偏粉 | 内置 **Perceptual OkLab** 引擎，沿人眼感知等色相线径向收敛 |
| 🛡️ **DWG 广色域黑洞防护** | DWG CIE 亮度权重中蓝色为负 (`-0.14775`)，极纯暗蓝易算成负亮度黑洞 | **Safe-Y `smax_c2` 亮度地板** + **虚色域安全融合**，彻底杜绝负值破损与折痕 |
| 🎞️ **黑位彩噪质感** | 绿色/品红彩噪直接消色后常变为刺眼的“亮白麻点” | **Chroma Density** 仅对高彩度像素做密度下沉，**中性灰阶绝对 0 变化** |
| 🔥 **背光暖肤色保留** | 一刀切抽干阴影，背光面人物肤色与暖光易发灰死板 | **Warm Skin Protect** 在 OkLab `+48°` 暖色扇区平滑避让，去冷噪留血气 |
| 📦 **3D LUT 烘培安全性** | 曲线斜率过陡时，33 点 LUT 跨格漏采产生暗部断层 | **纯逐像素运算** + **动态最小过渡跨度保护 (`0.085 ~ 0.14`)**，支持 33/65 点导出 |

---

## 🖼️ 效果对比（16-bit DWG/DI 专项测试卡）

使用仓库内置的真 16-bit 测试卡 [`DWG_DI_Shadow_Desat_TestChart_16bit.png`](DWG_DI_Shadow_Desat_TestChart_16bit.png) 经 `DWG/DI → Rec.709 Gamma 2.4` 转换后的四宫格实测对比：

<p align="center">
  <img src="assets/comparison_rec709.png" alt="DWG Shadow Desat 16-bit Test Chart Comparison" width="100%" />
</p>

- **① Original**：包含中性灰阶梯、7 色暗部渐变条、高强度暗部彩噪矩阵（绿噪 / DWG 极限蓝 / 品红青噪 / 近零黑位）、暖肤色球 vs 冷蓝球，以及内圈 `-3EV` / 外圈未处理等亮色轮。
- **② Film Rolloff Preset (`OkLab`, `Strength=0.85`, `Warm Protect=0.20`)**：左下角各类暗部彩噪矩阵被温和压平融入黑位，中灰 (`0.336`) 与高光区与原图保持像素级一致。
- **③ Highlight Preview (`Warm Skin Protect=0.80`)**：直观高亮显示受影响的暗部选区——受保护的中灰以上区域与暖肤色球/色轮暖色扇区被压为 18% 中灰。
- **④ Shadow Mask Preview (`Strength=0.85`, `Warm Skin Protect=0.80`)**：精确呈现最终消色权重遮罩，暖肤色区域平滑避让，冷蓝与彩噪区域吃满压制权重。

---

## 📐 核心原理与可视化

### 1. DI 编码域衰减曲线与 3D LUT 防断层跨度保护

权重曲线在 DaVinci Intermediate 码值域中基于 `Safe-Y` 亮度计算，并通过 `smooth3` 实现 $C^1/C^2$ 平滑起止；高于 `Shadow Pivot`（默认 `0.28`，低于 18% 中灰 `0.336`）的像素 **100% 零影响透传**：

<p align="center">
  <img src="assets/rolloff_curves.svg" alt="Shadow Rolloff Curves in DI Domain" width="100%" />
</p>

### 2. OkLab `+48°` 暖调 / 肤色定向保护窗口（洛伦兹色度软核）

在 OkLab $(a, b)$ 感知色度平面以 `+48°`（暖调肤色中心方向）构建**洛伦兹色度正则化余弦平方钟形窗**（Lorentzian-Regularized $\cos^2$ Field，正则尺度 $\sigma_C = 0.018$）：

$$w_{\text{warm}} = \frac{\max(a \cos 48^\circ + b \sin 48^\circ,\ 0)^2}{a^2 + b^2 + \sigma_C^2} \quad (\sigma_C = 0.018)$$

- **低色度自动退避**：极低色度的黑发、近中性阴影及视频压缩块不会因微弱色相角抖动触发保护跳变，始终保持常态压噪；
- **零平顶连续过渡**：消除固定角度阈值造成的等高线裁切硬边，在全额压制冷绿/青蓝/品红彩噪的同时，让暗部暖调血气随色度柔和渐入。

<p align="center">
  <img src="assets/warm_skin_polar.svg" alt="Warm Skin Protect Polar Response" width="100%" />
</p>

---

## 🗺️ 推荐节点树与色彩管线

本插件专为 **DaVinci Wide Gamut / DaVinci Intermediate (DWG / DI)** 编码设计，请务必确保输入该节点的画面处于 `DWG / DI` 状态（置于 **Input CST 之后、Output CST 之前**）：

```mermaid
flowchart LR
    A["📷 相机原始素材<br/>(S-Log3 / LogC4 / V-Log)"] --> B["🔄 Input CST<br/>相机空间 → DWG / DI"]
    B --> C["🎨 曝光 / 平衡 / 风格调色<br/>(DWG / DI 工作空间)"]
    C --> D["✨ DWG_Shadow_Desat<br/>暗部彩噪压制 & 胶片衰减"]
    D --> E["🔄 Output CST<br/>DWG / DI → Rec.709 G2.4"]
    E --> F["🖥️ 监看 / 交付成品"]

    style D fill:#1e3a5f,stroke:#38bdf8,stroke-width:2px,color:#f8fafc
```

---

## 📥 安装方法

1. 将本仓库中的 [`DWG_Shadow_Desat.dctl`](DWG_Shadow_Desat.dctl) 复制到达芬奇的 LUT 目录：
   - **Windows**：`C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT`（可在其下新建子文件夹，例如 `Custom_DCTL`）
   - **macOS**：`/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT`
2. 打开 DaVinci Resolve → 进入 **调色（Color）** 页面：
   - 在节点上添加 **Resolve FX 色彩 → DCTL**，在下拉列表中选择 `DWG_Shadow_Desat`。
   - 若列表未显示，前往 **项目设置 → 色彩管理 → 更新列表（Update Lists）** 刷新即可，或重启达芬奇。

> [!NOTE]
> 使用 DCTL 需要 **DaVinci Resolve Studio（收费版）**。若使用免费版，可将他人使用本 DCTL 导出的 `.cube` LUT 加载到免费版节点中使用。

---

## 🎛️ 参数详解（8 个核心控件）

> 为防止 Windows 版达芬奇对中文 UI 标签编译异常，插件面板采用英文标签，以下为逐项中文说明：

| 插件面板英文参数 | 中文含义 | 默认值与范围 | 作用与调节手感 |
| :--- | :--- | :--- | :--- |
| **1. Desat Engine** | **消色引擎** | `Perceptual OkLab` / `Linear Luma` | **`Perceptual OkLab`（默认推荐）**：在感知均匀空间消色，消除人眼 Abney 效应造成的“蓝偏紫、红偏粉”，暗部渐变极具胶片高级感；<br>**`Linear Luma`**：在线性空间严格锁定安全物理亮度 $Y$，适合纯工程向压制极暗彩噪。 |
| **2. Desat Strength** | **暗部消色力度** | `0.85` (`0.00 ~ 1.00`) | 控制最暗处（低于 `Black Floor`）的饱和度消除比例。<br>`1.0` = 最暗处完全退成纯净中性灰；`0.65 ~ 0.85` = 保留一丝有机的暗部底色。 |
| **3. Shadow Pivot** | **暗部起始阈值** | `0.28` (`0.09 ~ 0.60`) | 决定“从多亮开始介入降饱和”（DWG/DI 中灰 18% 约为 `0.336`）。<br>**高于此阈值的中灰与高光 100% 零影响（精确透传）**。 |
| **4. Black Floor** | **极暗满额阈值** | `0.08` (`0.00 ~ 0.35`) | 低于此阈值的极暗底噪区吃满 `Desat Strength` 设定的最大力度；`Black Floor` 与 `Shadow Pivot` 之间平滑过渡。 |
| **5. Rolloff Curve** | **衰减曲线形态** | `1.00` (`0.40 ~ 2.20`) | 控制过渡区的缓急：<br>`< 1.0` = 靠向中间调早早开始温柔滚落（胶片感）；<br>`> 1.0` = 紧贴极暗区收拢陡降（专注压底噪，少动次暗部）。 |
| **6. Chroma Density** | **色彩密度 / 亮暗补偿** | `-0.08` (`-0.50 ~ +0.30`) | **仅对有色像素生效，中性灰阶（$R=G=B$）绝对 0 变化**：<br>• **负值（如 `-0.08 ~ -0.20`）**：模仿胶片减色法密度感，让暗部绿/品红彩噪在消色的同时温和下沉融入黑位，避免“亮白麻点”；<br>• **正值（如 `+0.05 ~ +0.15`）**：补偿高饱和色彩去色后的 HK 视觉变暗感。 |
| **7. Warm Skin Protect** | **暗部暖调 / 肤色保护** | `0.00` (`0.00 ~ 1.00`) | 保护阴影中的红-橙-黄暖调（特别是背光面肤色、烛光/霓虹暖光）不被抽成死灰，同时对冷绿、青蓝、品红彩噪保持全额压制。<br>采用**洛伦兹色度正则化余弦平方钟形窗**（`+48°`，$\sigma_C = 0.018$）：极低色度的黑发与暗部噪块平滑退出保护，暗部肤色随色度柔和渐入且无高数值裁切感。 |
| **8. Preview - Set Off for LUT** | **预览模式** | `Off - LUT Safe` | **`Off - LUT Safe`**：正常画面输出（导出 LUT 前务必切回此项）；<br>**`Highlight`**：类似达芬奇限定器 `Shift+H` 高亮显示——选中的暗部保留显示处理后画面，未受影响的中灰/高光及被 `Warm Skin Protect` 保护的暖调肤色压成 18% 中灰（`0.336`），直观核查实际选区范围；<br>**`Shadow Mask`**：黑白权重遮罩（越白代表消色力度越大）；<br>**`Desat Delta 4x`**：4 倍放大显示被消除掉的色彩/噪点差值，便于检查是否误伤正常色彩。 |

### 💡 滑块联动与预览模式使用贴士

1. **33 点 LUT 最小过渡跨度防呆保护**：为防止将 `Shadow Pivot` 与 `Black Floor` 拉得过近导致导出 33 点或 65 点 LUT 时跨格漏采出现断层，插件内置了 `0.085 ~ 0.14`（随 `Rolloff Curve` 动态适配）的最小过渡跨度保护。当两者间距小于该安全跨度时，插件会**优先锁定 `Shadow Pivot` 不变**，并自动将实际生效的 `Black Floor` 下推到 `Shadow Pivot - min_span`（此时在上限附近微调 `Black Floor` 若画面无变化属于正常防断层保护）。
2. **`Highlight` 与 `Shadow Mask` 的分工**：`Highlight` 预览的是选区权重（即使 `Desat Strength = 0.0` 也能用来框选并检查 `Shadow Pivot` / `Black Floor` / `Warm Skin Protect` 的作用范围）；而 `Shadow Mask` 预览的是最终实际施加的消色力度（随 `Desat Strength` 缩放）。
3. **`Warm Skin Protect` 的平滑过渡特性**：即使将 `Warm Skin Protect` 拉高至 `0.80 ~ 1.00`，近中性灰的低色度区域（如黑发发丝、暗影底噪）也不会因微弱偏色发生角度撕裂，而在暗部肤色交界处会随色度连续羽化，避免 `Shadow Mask` 出现锯齿或等高线硬边。

---

## 🎯 三套实用参考预设

| 参数项 | 预设 1：纯净压暗部彩噪<br/>*(高 ISO 底噪专杀)* | 预设 2：胶片暗部自然衰减<br/>*(默认推荐起点)* | 预设 3：低调人像 / 夜景护肤<br/>*(去冷色杂噪、留暖色血气)* |
| :--- | :---: | :---: | :---: |
| **Desat Engine** | `Linear Luma` / `Perceptual OkLab` | `Perceptual OkLab` | `Perceptual OkLab` |
| **Desat Strength** | `1.00` | `0.85` | `0.90` |
| **Shadow Pivot** | `0.16` | `0.28` | `0.32` |
| **Black Floor** | `0.05` | `0.08` | `0.10` |
| **Rolloff Curve** | `1.60` | `1.00` | `0.90` |
| **Chroma Density** | `-0.15` *(防绿噪变白点)* | `-0.08` | `-0.05` |
| **Warm Skin Protect** | `0.00` | `0.20` | `0.80` |

---

## 📦 配合达芬奇「生成 LUT」的操作规范

本插件在底层专门加入了纯逐像素点运算、纯黑/中性灰锚定与动态 3D LUT 跨度保护，可直接配合达芬奇的 **生成 LUT（Generate LUT）** 功能使用：

> [!IMPORTANT]
> 导出前请务必确认 **`Preview - Set Off for LUT` 已切回 `Off - LUT Safe`**，否则会将黑白遮罩或高亮预览直接烤入 `.cube` 文件中。

| 应用场景 | 推荐 LUT 精度 | 10,000 点四面体插值仿真精度 |
| :--- | :---: | :--- |
| **常规胶片衰减预设** (`Pivot >= 0.25`, `Curve <= 1.2`) | **33 点 / 65 点 `.cube`** | 33 点 RMS 误差仅 `0.00031` |
| **陡峭极暗压噪预设** (`Pivot <= 0.18`, `Curve >= 1.5`) | **优先 65 点 `.cube`** | 65 点 RMS 误差 `0.00021`，最大误差 `< 0.0019` |

**一并烤入风格 LUT 的步骤**：将包含 `Input CST`、`DWG_Shadow_Desat`、你的调色节点和 `Output CST` 的节点树（确保节点树中不含降噪、光晕、颗粒等空间滤波插件）合并后右键 → **生成 LUT → 65 点立方体（65 Point Cube）**。

---

## 🧪 自动化验证与测试卡

仓库内置了 1:1 GPU `float32` 数学行为仿真及 33/65 点 3D LUT 精度回归脚本，以及真 16-bit DWG/DI 专项测试卡生成脚本（依赖 `numpy`、`Pillow`）：

```bash
# 运行色彩科学不变量、Safe-Y、C2 平滑性与 33/65-pt LUT 插值精度验证
python tests/verify_dctl.py

# 重新生成 16-bit DWG/DI 测试卡与 Rec.709 模拟预览图
python tests/generate_test_chart.py
```

---

## 📂 项目文件结构

```text
dwg-shadow-desat-dctl/
├── DWG_Shadow_Desat.dctl                  # 核心 DCTL 插件源码（直接放入达芬奇 LUT 目录）
├── DWG_DI_Shadow_Desat_TestChart_16bit.png # 1920×1080 真 16-bit DWG/DI 专项测试卡
├── README.md                              # 中文项目说明书与技术文档
├── assets/                                # README 视觉图表与图标资源
│   ├── banner.svg                         # 项目主横幅与矢量徽标
│   ├── comparison_rec709.png              # 16-bit 测试卡 2×2 实测效果对比图
│   ├── rolloff_curves.svg                 # DI 域衰减曲线与透传区图示
│   └── warm_skin_polar.svg                # OkLab +48° 暖调肤色保护极坐标响应图
└── tests/
    ├── verify_dctl.py                     # 色彩科学 & 33/65 点 3D LUT 插值精度验证脚本
    ├── generate_test_chart.py             # 16-bit 测试卡生成脚本
    └── preview_rec709.png                 # 测试卡 Rec.709 模拟预览图
```

---

## 📝 更新日志

### 2026-11-23 — `Warm Skin Protect` 洛伦兹软核算法升级
- **消除高数值下的硬边裁切感**：将 [DWG_Shadow_Desat.dctl](DWG_Shadow_Desat.dctl) 中的暖肤色保护权重重构为 **洛伦兹色度正则化余弦平方钟形窗**（Lorentzian-Regularized $\cos^2$ Field，OkLab `+48°` 轴，$\sigma_C = 0.018$）。
- **消除低色度暗部边缘撕裂**：黑发、近中性阴影及视频压缩块等极低色度区域平滑退出保护，不再因微弱色相角抖动触发跳变；中高色度暗部肤色交界处呈现连续羽化渐变，保留立体层次。
- **文档与可视化同步**：同步更新 [`tests/verify_dctl.py`](tests/verify_dctl.py)、[`assets/warm_skin_polar.svg`](assets/warm_skin_polar.svg) 极坐标响应图、[`assets/comparison_rec709.png`](assets/comparison_rec709.png) 四宫格实测对比图及本 README，全部 9 项自动化回归测试均已通过。
