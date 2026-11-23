# DWG_Shadow_Desat.dctl 使用指南

专精于 **DaVinci Wide Gamut / DaVinci Intermediate (DWG / DI)** 工作空间的暗部降饱和 DCTL 插件。  
针对达芬奇原生 `Lum vs Sat` 容易出现的“越降越暗”“暗部蓝/红偏色”“黑位灰噪麻点”以及“3D LUT 导出断层”等问题，从底层色彩科学重新设计，兼顾 **压制暗部彩噪** 与 **胶片暗部柔和色彩衰减**。

---

## 一、安装方法

1. 将本目录下的 `DWG_Shadow_Desat.dctl` 复制到达芬奇的 LUT 目录：
   - **Windows**：`C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT`（也可在其下新建子文件夹，例如 `Custom_DCTL`）
   - **macOS**：`/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT`
2. 打开 DaVinci Resolve → 进入 **调色（Color）** 页面：
   - 在节点上添加 **Resolve FX 色彩 → DCTL**（或直接打开项目设置刷新 LUT）。
   - 若列表未显示，在 **项目设置 → 色彩管理 → 更新列表（Update Lists）** 刷新即可，或重启达芬奇。

> **注**：使用 DCTL 需要 **DaVinci Resolve Studio（收费版）**。如果未购买 Studio 版，也可以将朋友或他人用本 DCTL 导出的 `.cube` LUT 加载到免费版中。

---

## 二、推荐节点树位置（重要）

本插件专为 **DaVinci Wide Gamut / DaVinci Intermediate (DWG / DI)** 编码设计，请务必确保输入该节点的画面处于 `DWG / DI` 状态：

- **节点位置**：放在 **输入 CST（相机 Log → DWG/DI）之后、输出 CST（DWG/DI → Rec.709）之前**。
- **典型节点顺序参考**：
  1. `Input CST`（相机空间 → DWG / DI）
  2. `曝光 / 平衡 / 风格调色`
  3. **`DWG_Shadow_Desat`**（在 DWG/DI 空间完成暗部彩噪压制与胶片衰减）
  4. `Output CST`（DWG / DI → Rec.709 Gamma 2.4）

---

## 三、参数详解（8 个核心控件）

> 为防止 Windows 版达芬奇对中文 UI 标签编译异常，插件面板采用英文标签，以下为逐项中文说明：

| 插件面板英文参数 | 中文含义 | 默认值与范围 | 作用与调节手感 |
| :--- | :--- | :--- | :--- |
| **1. Desat Engine** | **消色引擎** | `Perceptual OkLab` / `Linear Luma` | **`Perceptual OkLab`（默认推荐）**：在感知均匀空间消色，消除人眼 Abney 效应造成的“蓝偏紫、红偏粉”，暗部渐变极具胶片高级感；<br>**`Linear Luma`**：在线性空间严格锁定安全物理亮度 $Y$，适合纯工程向压制极暗彩噪。 |
| **2. Desat Strength** | **暗部消色力度** | `0.85` (`0.0 ~ 1.0`) | 控制最暗处（低于 `Black Floor`）的饱和度消除比例。<br>`1.0` = 最暗处完全退成纯净中性灰；`0.65 ~ 0.85` = 保留一丝有机的暗部底色。 |
| **3. Shadow Pivot** | **暗部起始阈值** | `0.28` (`0.09 ~ 0.60`) | 决定“从多亮开始介入降饱和”（DWG/DI 中灰 18% 约为 `0.336`）。<br>**高于此阈值的中灰与高光 100% 零影响（精确透传）**。 |
| **4. Black Floor** | **极暗满额阈值** | `0.08` (`0.00 ~ 0.35`) | 低于此阈值的极暗底噪区吃满 `Desat Strength` 设定的最大力度；`Black Floor` 与 `Shadow Pivot` 之间平滑过渡。 |
| **5. Rolloff Curve** | **衰减曲线形态** | `1.00` (`0.40 ~ 2.20`) | 控制过渡区的缓急：<br>`< 1.0` = 靠向中间调早早开始温柔滚落（胶片感）；<br>`> 1.0` = 紧贴极暗区收拢陡降（专注压底噪，少动次暗部）。 |
| **6. Chroma Density** | **色彩密度 / 亮暗补偿** | `-0.08` (`-0.50 ~ +0.30`) | **仅对有色像素生效，中性灰阶（$R=G=B$）绝对 0 变化**：<br>- **负值（如 `-0.08 ~ -0.20`）**：模仿胶片减色法密度感，让暗部绿/品红彩噪在消色的同时温和下沉融入黑位，避免“亮白麻点”；<br>- **正值（如 `+0.05 ~ +0.15`）**：补偿高饱和色彩去色后的 HK 视觉变暗感。 |
| **7. Warm Skin Protect** | **暗部暖调 / 肤色保护** | `0.00` (`0.00 ~ 1.00`) | 保护阴影中的红-橙-黄暖调（特别是背光面肤色、烛光/霓虹暖光）不被抽成死灰，同时对冷绿、青蓝、品红彩噪保持全额压制。 |
| **8. Preview - Set Off for LUT** | **预览模式** | `Off - LUT Safe` | **`Off - LUT Safe`**：正常画面输出（导出 LUT 前务必切回此项）；<br>**`Highlight`**：类似达芬奇限定器 `Shift+H` 高亮显示——选中的暗部保留显示处理后画面，未受影响的中灰/高光及被 `Warm Skin Protect` 保护的暖调肤色压成 18% 中灰（`0.336`），方便直观查看实际选区范围；<br>**`Shadow Mask`**：黑白权重遮罩（越白代表消色力度越大）；<br>**`Desat Delta 4x`**：4 倍放大显示被消除掉的色彩/噪点差值，便于检查有没有误伤正常色彩。 |

### 滑块联动与预览模式使用贴士
1. **33 点 LUT 最小过渡跨度防呆保护**：为防止将 `Shadow Pivot` 与 `Black Floor` 拉得过近导致导出 33 点或 65 点 LUT 时跨格漏采出现断层，插件内置了 `0.085 ~ 0.14`（随 `Rolloff Curve` 动态适配）的最小过渡跨度保护。当两者的间距小于该安全跨度时，插件会**优先锁定 `Shadow Pivot` 不变**，并自动将实际生效的 `Black Floor` 下推到 `Shadow Pivot - min_span`（此时在上限附近微调 `Black Floor` 若画面无变化属于正常防断层保护）。
2. **`Highlight` 与 `Shadow Mask` 的分工**：`Highlight` 预览的是选区权重（即使 `Desat Strength = 0.0` 也能用来框选并检查 `Shadow Pivot` / `Black Floor` / `Warm Skin Protect` 的作用范围）；而 `Shadow Mask` 预览的是最终实际施加的消色力度（随 `Desat Strength` 缩放）。

---

## 四、三套实用参考预设

### 预设 1：纯净压暗部彩噪（保留次暗部原色，专杀高 ISO 底噪）
- **Desat Engine**：`Linear Luma` 或 `Perceptual OkLab`
- **Desat Strength**：`1.00`
- **Shadow Pivot**：`0.16`
- **Black Floor**：`0.05`
- **Rolloff Curve**：`1.60`
- **Chroma Density**：`-0.15`（防止绿色噪点变白麻点）
- **Warm Skin Protect**：`0.00`

### 预设 2：胶片暗部自然色彩衰减（默认推荐起点）
- **Desat Engine**：`Perceptual OkLab`
- **Desat Strength**：`0.85`
- **Shadow Pivot**：`0.28`
- **Black Floor**：`0.08`
- **Rolloff Curve**：`1.00`
- **Chroma Density**：`-0.08`
- **Warm Skin Protect**：`0.20`

### 预设 3：低调人像 / 夜景暗部护肤（去冷色杂噪、留暖色血气）
- **Desat Engine**：`Perceptual OkLab`
- **Desat Strength**：`0.90`
- **Shadow Pivot**：`0.32`
- **Black Floor**：`0.10`
- **Rolloff Curve**：`0.90`
- **Chroma Density**：`-0.05`
- **Warm Skin Protect**：`0.80`

---

## 五、配合达芬奇「生成 LUT」的操作规范

本插件在底层专门加入了纯逐像素点运算、纯黑/中性灰锚定与动态 3D LUT 跨度保护，可直接配合达芬奇的 **生成 LUT（Generate LUT）** 功能使用。操作时请注意以下两点：

1. **导出前务必检查 `Preview` 开关**：
   - 确保 **`Preview - Set Off for LUT` 处于 `Off - LUT Safe`**，否则会把黑白遮罩烤进 `.cube` 文件里。
2. **推荐导出的 LUT 精度**：
   - **常规胶片衰减预设**（如 `Pivot >= 0.25`、`Curve <= 1.2`）：导出 **33 点或 65 点 `.cube`** 均与原 DCTL 高度一致（经 10,000 点仿真验证，33 点四面体插值 RMS 误差仅 `0.00031`）。
   - **陡峭极暗压噪预设**（如 `Pivot <= 0.18` 且 `Curve >= 1.5`）：**建议优先选择 65 点 `.cube`**（65 点 RMS 误差 `0.00021`，最大误差 `< 0.0019`），暗部过渡更无损。
3. **如何一并烤进风格 LUT**：
   - 将包含 `Input CST`、`DWG_Shadow_Desat`、你的调色节点和 `Output CST` 的节点树（确保节点树中不含降噪、光晕、颗粒等空间滤波插件）合并右键 → **生成 LUT → 65 点立方体（65 Point Cube）**。

---

## 六、项目文件结构

- `DWG_Shadow_Desat.dctl`：核心插件源码（可直接放入达芬奇 LUT 目录使用）。
- `DWG_DI_Shadow_Desat_TestChart_16bit.png`：1920×1080 真 16-bit DWG/DI 专项测试卡（导入达芬奇后在其后挂载 `DWG/DI → Rec.709` CST，可用于对比原生 `Lum vs Sat`、`Linear Luma`、`Perceptual OkLab` 及导出 LUT 的波形、矢量示波器与暗部彩噪表现）。
- `tests/verify_dctl.py`：全自动色彩科学及 33/65 点 3D LUT 插值精度验证脚本。
- `tests/generate_test_chart.py`：16-bit DWG/DI 测试卡生成脚本（含 Rec.709 模拟预览图输出）。
- `README.md`：本说明文档。
