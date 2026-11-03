# 展示资产与下载

Git 只跟踪源码、文档、小型输入和轻量 JPEG。MP4/SPZ 放在 [v0.10.2 Release](https://github.com/river-ya/world-scene/releases/tag/v0.10.2)。

| 附件 | 内容 |
| --- | --- |
| paired-room40-side-by-side.mp4 | 左 LucidDreamer、右 FlashWorld 的同步视频 |
| flashworld-room-left40.spz | 对应 FlashWorld 运行的压缩三维高斯 |
| SHA256SUMS | 附件的 SHA256 |

SPZ 需要支持 3D Gaussian Splatting/SPZ 的查看器，不是普通三角网格。相机、坐标和球谐支持可能因查看器而异，先与视频核对。PLY 可通过复现运行导出，不为上传而改名为 GLB。

~~~bash
sha256sum -c SHA256SUMS
~~~

输入来源、相机和模型身份见 [冻结样例](../examples/paired-room40/)，展示方法与限制见 [RESULTS.md](RESULTS.md)。输入来自作者代码中的官方示例，第三方权利不由本仓库重新授予。

不上传模型权重，按 configs/versions.lock.json 和 configs/lucid.lock.json 的固定地址准备。现有 .gitignore 和 check_public.py 继续排除推理输出、私有环境和凭据。新增展示时使用匿名化元数据和新 Release，保留版本及摘要。
