# LucidDreamer 适配与来源

当前相机入口为 [v0.10.0 多样视角指南](CURRENT_EXPERIMENTS.md)：十例分别使用 35°–65° 的不同水平转角，固定中心、输入首帧、左右搭配及起止缓动。以下原路径/生成顺序说明描述 v0.7.0 历史协议；新版相机不再沿用原 room/studio 路径。

原始方法：[LucidDreamer: Domain-free Generation of 3D Gaussian Splatting Scenes](https://arxiv.org/abs/2311.13384)，作者代码固定 `4ddf48563140c4254c8ce566955d12531b46829c`。本项目将运行所需源码子集放在 `upstream/LucidDreamer`；保留原文件版权头与 LICENSE。`configs/lucid.lock.json` 分别记录原始文件和适配后文件 SHA256。

## 源码改动

1. `luciddreamer.py`：输入图已经按 FlashWorld 固定裁剪预处理，替换默认方形补图/裁剪分支为尺寸检查，SD 补图显式传入宽高，避免 diffusers 自动退回 512×512；PCD 补图与逐场景高斯优化加进度输出；可见点不足时提前失败。Dreaming、深度对齐和高斯损失/优化配方沿用作者实现。
2. ZoeDepth 内 `models/base_models/midas.py`：将动态 Torch Hub GitHub 入口改成本地 `LUCID_MIDAS_SOURCE`。MiDaS 固定作者 v3_1 提交 `1645b7e1675301fdfac03640738fe5a6531e17d6`，不再隐式拉取可变分支或 ImageNet 初始化权重。
3. 其余适配在 `tools/lucid_runtime.py` 中：使用本地 SD fp16 safetensors 和 ZoeDepth checkpoint；替代只支持方形的默认相机读取，支持实际 fx/fy/cx/cy；训练目标图留在 CPU，单步移动目标图到 GPU；生成完成后释放 SD/ZoeDepth；视频逐帧编码，避免把整段 RGB/深度视频留在内存。

## 相机与数值约定

- v0.10.0：`tools/lucid_cameras.py` 在原始输入裁剪前替换相机位姿，保留输入相机内参；生成顺序为 0–23，视频为同一路径的 346 帧插值。`lucid_inputs.relative_cameras` 支持显式正参考尺度，以兼容固定中心轨迹；`protocol.json` 和 manifest 保存新协议与角度，`flashworld.json` 保存可复现的成对输入。新相机同时用于 Dreaming 和最终资产重载渲染，需要重新生成场景。
- FlashWorld 相机为 OpenGL c2w（朝 −Z，Y 向上），LucidDreamer 点云生成使用 CV w2c（朝 +Z，Y 向下）。工具使用输入锚点的局部 CV 坐标系；相机旋转和位置均转换，不能只翻转四元数某一项。
- 平移分母为原相机相对第一个相机的最大距离加 0.01，与固定 FlashWorld `normalize_cameras` 相同。锚点改为局部原点只是刚体变换，不改变相对路径。
- FlashWorld 在像素 `u+0.5,v+0.5` 处发射射线；LucidDreamer 原始点云代码使用整数像素，因此 PCD 内参主点减 0.5。GPU 投影矩阵使用对应 NDC→像素中心映射，避免半像素偏差，并支持非中心主点与非方形视场角。
- 原路径 24 个视角及 346 帧、15 fps 渲染顺序保持。生成顺序从输入锚点开始，先向路径起点扩展，再向末端扩展；内部五个 hemisphere 对齐视角是原方法组成部分。
- ZoeDepth 原生深度不按 FlashWorld 输出进行事后拟合。模型几何的米制尺度一致性未经验证，manifest 明确记录 `metric_scale_alignment`。本版不输出未经验证的“正式 WorldScore 排名”。

## 源码、权重和环境

- GLM 头文件来自作者 `0.9.9.8`，提交 `bf71a834948186f4097caa076cd2663c69a10e1e`，保留 copying.txt；仅供两个作者 CUDA 扩展编译，不替换系统库。
- 默认 SD 权重来自 `stable-diffusion-v1-5/stable-diffusion-inpainting` 固定 revision `8a4288a76071f7280aedbdb3253bdb9e9d5d84bb`。源代码旧 `fp16` 分支当前不存在，本版用固定快照的 `.fp16.safetensors`，加载时指定 `variant='fp16'`；不自动换成其他风格 checkpoint。
- ZoeDepth 使用作者 GitHub release 的 `ZoeD_M12_N.pt`。首次下载摘要是下载回执，不伪称作者签名或作者预公布校验值。后续完整校验拒绝文件摘要变化；每次运行归档实际摘要。
- Python 3.9 / torch 2.0.1 cu118 与 CUDA 11.8 / GCC 11 独立于 FlashWorld。顶层依赖固定，安装后同时保存 pip freeze 与 conda explicit 清单。

本项目封装与适配文件及所携带第三方源码分别遵循其来源许可；研究复现发布保留作者署名、原许可证与改动说明。
