# 公开版 v0.10.2 验证记录

日期：2026-11-03。源码来自内部 v0.10.0，身份见 configs/publication.json。公开整理没有重新训练，也没有把历史 GPU 结果改写成 v0.10.2 新实测。

## 本次实际检查

- 独立 CPU 环境、真实冻结开发图片：发现 60 项测试，56 项通过，4 项因缺少 plyfile 明确跳过。没有将跳过计作通过。
- 新增同条件作业检查：脚本被 Slurm 移到 spool 后仍能找到原配置、输入和环境；seed=0；成功或失败均清理自己的临时目录。
- 同步了原子 JSON 回执、多样 LucidDreamer 相机、wideview 与已有模拟调度检查。
- 全部 Slurm 脚本通过 bash -n；当前 README、SLURM、GITHUB、CURRENT_EXPERIMENTS、PAIRED_COMPARISON 的 33 个 Bash 块通过语法检查。
- check_public.py 的固定第三方源码、补充许可证摘要、10 MiB 单文件预算和私有文件/常见凭据模式检查通过。
- 原同条件归档 SHA256、两模型 manifest 以及每个已记录输入/输出摘要逐项通过，原运行均为 complete。
- README 和本次新增文档的本地链接已核对。模型权重、原始日志、完整 PLY、个人部署路径及凭据不进入 Git。

CPU 测试使用临时的外部数据目录映射，结束即删除；模拟调度和导出测试使用 TemporaryDirectory。没有清理或改写原实验资产。

## GPU 证据的来源

内部 v0.10.0 的 LucidDreamer 十例已完成；客厅同条件 FlashWorld、LucidDreamer 和白底重渲染也有完成记录。公开的预览、视频与 SPZ 从这些真实输出提取，源版本、摘要和硬件见 examples/paired-room40/result-summary.json。

技术完成不能代替视觉质量。结果保留失败模式、同条件限制、无未知区域真值及跨模型尺度未标定等说明。此公开整理本身未提交新 GPU 作业。

## CI 范围

GitHub Actions 仅运行公开源码检查、标准库测试和 Shell 语法检查。不下载数十 GB 权重，也不执行 GPU 生成；缺少外部图片或依赖时的 skipped 均保留。


## 首次远端 CI 暴露的问题与修复

v0.10.1 首次 CI 因几何单元测试意外读取外部开发图片而失败。v0.10.2 将该单元测试改用内嵌官方图片，仍覆盖十种角度、保真和源输入不变；真正依赖开发图片的集成检查加上明确的存在性条件。模型推理代码未因该 CI 修复改变。无外部依赖的标准库路径也在本地复测。

标准库环境（无外部开发图片、无 NumPy/Pillow/torch）：发现 52 项，40 项通过、12 项明确跳过，退出成功。
