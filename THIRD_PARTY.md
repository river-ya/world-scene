# 第三方代码与论文

本仓库的工作是模型接入、离线资产校验、实验输入适配、Slurm 编排和结果追溯；模型方法归原作者所有。

| 组件 | 固定来源 | 本地许可 |
| --- | --- | --- |
| FlashWorld | [作者仓库](https://github.com/imlixinyang/FlashWorld)，`424db4487de308a39e5137afbe85e7568a96193f` | [Apache 2.0](upstream/FlashWorld/LICENSE) |
| LucidDreamer（SNU CVLab） | [作者仓库](https://github.com/luciddreamer-cvlab/LucidDreamer)，`4ddf48563140c4254c8ce566955d12531b46829c` | [CC BY-NC-SA 4.0](upstream/LucidDreamer/LICENSE) |
| ZoeDepth | 上述 LucidDreamer 源码包含的子目录 | [MIT](upstream/LucidDreamer/ZoeDepth/LICENSE) |
| MiDaS | [作者仓库](https://github.com/isl-org/MiDaS)，`1645b7e1675301fdfac03640738fe5a6531e17d6` | [MIT](upstream/MiDaS/LICENSE) |
| GLM | [作者仓库](https://github.com/g-truc/glm)，`bf71a834948186f4097caa076cd2663c69a10e1e` | [原始 copying.txt](upstream/glm/copying.txt) |
| depth-diff-gaussian-rasterization-min | LucidDreamer 内含扩展 | [Gaussian-Splatting License](upstream/LucidDreamer/submodules/depth-diff-gaussian-rasterization-min/LICENSE.md) |
| simple-knn | LucidDreamer 内含扩展，源码保留 Inria 版权头 | [Gaussian-Splatting License](upstream/LucidDreamer/submodules/simple-knn/LICENSE.md) |

固定 LucidDreamer 提交的 simple-knn 子目录没有携带其源码头引用的 LICENSE.md。本公开版从 [simple-knn 原项目](https://gitlab.inria.fr/bkerbl/simple-knn/-/raw/main/LICENSE.md) 补入原文；下载日期、文件摘要和来源记在 [publication.json](configs/publication.json)。该文件不冒充来自上述 LucidDreamer 固定提交。

FlashWorld 按文件摘要锁定，除了不携带无运行意义的 `.DS_Store`，没有改写其源文件。其他上游目录包含运行所需源码子集；LucidDreamer 的补图尺寸、离线深度加载等适配及原始/当前文件摘要分别见 [适配说明](docs/LucidDreamer适配说明.md) 和 [lucid.lock.json](configs/lucid.lock.json)。第三方 README 可能引用未随子集分发的训练工具，本项目实际入口以根 README 为准。

论文与任务依据：

- [FlashWorld: High-quality 3D Scene Generation within Seconds](https://arxiv.org/abs/2510.13678)：单图/文本条件 3D 场景生成。
- [LucidDreamer: Domain-free Generation of 3D Gaussian Splatting Scenes](https://arxiv.org/abs/2311.13384)：图文条件下的场景扩展和高斯场景构建。
- [WorldScore](https://haoyi-duan.github.io/WorldScore/)：显式相机控制、场景生成质量和一致性评估参考。

模型权重与数据没有放入本仓库。下载工具中的固定 revision/摘要用于复现，不替代其各自使用条款。
