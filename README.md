# World Scene

**单图与文本条件下的三维场景生成、相机控制和模型对照实验。**

本仓库提供 FlashWorld 与 SNU CVLab LucidDreamer 的研究复现封装，包含离线权重校验、固定输入与相机协议、Slurm 作业、可追溯结果导出。当前公开源码版为 **v0.8.1**，由内部实验版 v0.8.0 整理；不是新提出的模型方法。

## 当前能力

| 模块 | 内容 | 验证范围 |
| --- | --- | --- |
| FlashWorld | 单张图＋文本 → 3D Gaussian 场景、PLY/SPZ 和 MP4 | 既有室内案例已在 RTX 4090 完成推理；没有正式定量排名 |
| 同图多角度 | 同一客厅图水平向左 30° / 45° / 75°，固定相机中心、其他条件一致 | CPU 相机与流程验证通过；新轨迹的 GPU 视觉验收待完成 |
| LucidDreamer | 图文条件生成、逐场景高斯优化及视频导出 | 工程/CPU 检查通过；完整 4090 推理待验收 |
| 复现支持 | 固定源码/权重 revision，资产摘要、输入快照、环境清单、失败记录 | 不依赖个人服务器地址 |

当前任务是静态场景补全与新视角生成。LucidDreamer 的逐场景高斯优化不是基础扩散模型微调；仓库没有已验收的基础模型训练入口。网页展示可使用离线生成的 MP4，本项目不承诺在线实时生成。

## 快速开始

1. 将本仓库克隆或源码包解压到 Linux/WSL，进入仓库目录。`upstream/` 已包含锁定源码快照，**无需运行 git submodule update**。
2. 先做不需要 GPU、权重或第三方 Python 库的检查：

```bash
python3 -B tools/check_public.py
python3 -B -m unittest discover -s tests -v
```

没有外部开发图片、NumPy/Pillow/torch 时，部分测试会明确标记 skipped；这不代表完整 GPU 验证成功。完整本地验证范围见 [验证说明](docs/PUBLIC_VALIDATION.md)。

3. 按 [Slurm 完整执行指南](docs/SLURM.md) 配置自己的路径、环境和队列，下载模型/数据，先 check 与单例，再开展三档相机对照。FlashWorld 与 LucidDreamer 使用两个独立环境。
4. 自己建立 GitHub 仓库时，按 [上传与维护指南](docs/GITHUB.md) 推送解压后的源码，而非把 ZIP 当作仓库唯一文件。

## 目录

```text
configs/           固定源码、模型资产、开发/测试划分与公开版来源记录
slurm/             FlashWorld 检查、推理及数组作业
slurm/lucid/       第二模型独立环境和作业
tools/            数据/资产准备、相机适配、运行与导出工具
tests/            单元及 CPU/调度流程测试
upstream/          附许可的固定第三方源码快照
docs/             操作指南、协议、历史验证及适配说明
```

主要入口：`tools/experiment.py`（FlashWorld），`tools/angles.py`（三档相机），`tools/lucid.py`（第二模型）。

## 环境与资源

- FlashWorld：Python 3.10、torch 2.6.0/cu124；先按脚本安装固定依赖及 CUDA 扩展。已跑通的本地任务使用 96G 主存、8 CPU、RTX 4090 单卡。64G 曾在模型量化阶段 OOM。
- LucidDreamer：独立 Python 3.9、torch 2.0.1/cu118、CUDA 11.8/GCC 11；运行资源仍待 GPU 实测。
- 现有 FlashWorld 展示案例在所用集群每例约一小时，受加载、offload 和硬件影响，不能当成论文速度复现。
- 代码不包含权重、数据集、环境、实验输出或个人配置。模型和数据单独存储，使用锁定的下载/校验工具准备。

## 对照实验的边界

已有 gallery 案例包含不同轨迹，适合展示多样性；模型对比应对齐同一张图片、文本、裁剪与相机条件。当前 LucidDreamer 入口仍对应原 gallery 协议，尚未接入新的纯旋转三档协议。跨模型物理尺度未校准，不宣称正式 WorldScore 排名。

单图没有未知区域真值：当前评估合理补全与跨视角一致性；准确恢复真实未见场景需要多视角真值。纯旋转不等同于解除遮挡后的背面重建。

## 来源与许可

模型及数据选择依据 [FlashWorld](https://arxiv.org/abs/2510.13678)、[LucidDreamer](https://arxiv.org/abs/2311.13384) 和 [WorldScore](https://haoyi-duan.github.io/WorldScore/)。详见 [第三方来源与许可证](THIRD_PARTY.md) 及 [LucidDreamer 适配](docs/LucidDreamer适配说明.md)。

自有封装的公开许可证尚未由维护者指定，第三方代码分别保留原许可；整个仓库并非统一 MIT 授权。见 [许可证范围](LICENSING.md)。

`docs/` 中带历史说明的中文文档用于记录协议演变，已替换个人部署信息；公开版实际运行以 `docs/SLURM.md` 为准。原始实验身份记在历史文档中，公开版不将历史结果改写成新版 GPU 实测。
