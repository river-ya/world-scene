# WorldModels Baseline：五部分研究展示

中文版静态网站：导航、按钮、场景名、轨迹标签、实验设置与架构说明均使用中文。保留 Open Sans 英文字体、原始输入 text、模型与项目专名；中文使用本地 Noto Sans SC 字体子集。原始输入图轮播、视频上方完整输入 text、静音自动播放均保留。目标地址为 https://river-ya.github.io/world-scene/ 。部署使用 river-ya/world-scene 的独立 website 分支，main 保留科研源码和发布工作流；本轮发布状态以线上核验为准。没有提交 GPU / Slurm 作业。

## 启动与构建

只需 Python 3.10+，不依赖 Node/npm、模型环境或后端。WSL/bash 执行：

```bash
cd '/mnt/d/aaaoffice/科研实习/轮转科研项目/项目1/worldmodels_baseline'
python3 -B tools/site.py build
python3 -B tools/site.py preview
```

打开 **http://127.0.0.1:8000/world-scene/**。已有预览服务时构建后 Ctrl+F5 刷新即可；新启动服务用 Ctrl+C 退出。端口冲突可使用 `python3 -B tools/site.py preview --port 8001`。服务器只暴露本站 `dist/`，支持视频 Range 请求。

```bash
python3 -B tools/site.py check
# 限定删除本站 dist 与 tools/tests 的 Python 缓存
python3 -B tools/site.py clean
python3 -B tools/site.py build
```

## 导航

顶部导航采用分块按钮，使用深色文字、明确边框和深绿色当前栏目状态。滚动页面时保持可见，并自动高亮所在栏目；手机菜单使用两列模块布局。

## 页面精简

图片与视频下方不再显示说明小字、案例统计、素材备注和实验信息展开区；输入图片下方的名称与序号也取消显示。对比模型名称移到视频上方。保留原始输入 text、播放控件、主要比较分析和架构模块说明，移除能力范围提示。素材版本、来源和校验记录仍在数据配置中维护。此轮通过 JavaScript 语法检查与静态构建。

## 当前五部分

| 部分 | 实际接入 | 交互与说明 |
| --- | --- | --- |
| FlashWorld | 16 个展示条目：原有3例、v0.6.0 varied 7例、v0.9.0 wideview 6例 | 图片轮播 → 精确文本 → 对应视频，保留不同版本和相机条件 |
| LucidDreamer | v0.10.0 归档10例 | 同样的轮播方式，保留其原相机/文本变体和渲染 |
| 配对比较 | paired-room40-74470 的两个白底视频 | 左 LucidDreamer，右 FlashWorld，同步播放/暂停/归零/公共时间轴；附4张真实配对帧、条件记录和差异分析 |
| 转角实验 | v0.8.0 的30°、45°、75° | 同一输入和文本，选择不同预渲染轨迹；输入图不随角度改变 |
| 模型架构 | 用户提供的 FlashWorld 与 LucidDreamer 原始 SVG 架构图 | 原图展示与点击放大；直观理解、机制比较与论文/代码链接 |

共有 **28 个配置案例、31 条视频**；26个方法展示条目、1个配对案例（2视频）、1个角度案例（3视频）。这些条目涉及 **8张来源图**，不把同图不同轨迹或文本变体计为独立来源图。

结果 MP4 是原文件逐字节副本，保持704×480、15 fps；大多数时长约23.07秒。初始仅加载当前可见案例的视频，其他方法/角度按需加载。静态产物约248 MiB，最大单视频11.99 MiB；以构建校验的实际输出为准。

## 证据和事实范围

- `src/data/provenance.json` 记录来源相对路径、输入快照和摘要、视频/输入/封面 SHA-256。导入时逐条对照 manifest，完成整段 CPU 解码与输入图检查。
- 原始 `visual_acceptance` 状态保留在来源记录中。网页的 `ready` 是可展示媒体状态，不改写原实验的科研验收状态。
- 配对条件来自 `paired-room40-74470/comparison/conditions.json`，公开副本为 `src/data/paired-conditions.json`。两侧实际用户输入 JSON 相同；档案记录相同像素、内参、24个生成相机、346个渲染相机、白底及 seed 整数。米制尺度未建立。
- LucidDreamer 第三部分使用既有 PLY 的白底重渲染；第二部分使用原归档视频。前者不是新一轮场景生成或优化。
- 真实帧的可见差异：起始视角两侧接近；后段 LucidDreamer 左侧新增区域有碎片、纹理拉伸与拼接边界，而 FlashWorld 对应画面更连贯。没有未知区域真值，不能认定生成物体就是真实隐藏物体。
- “联合多视图/三维反馈减少顺序深度融合误差”是基于方法和观察的机制解释，没有模块消融确定本例的因果，也不声称 FlashWorld 永远没有伪影。
- “直观理解”下的加噪/未知区域插图是原有可视化，未改动模型实验素材。

## 架构来源

[FlashWorld 方法第3节](https://arxiv.org/html/2510.13678v1#S3)及本地固定上游 `world_scene/upstream/FlashWorld/app.py`、`models/reconstruction_model.py`；[LucidDreamer 方法第3节](https://arxiv.org/html/2311.13384v2#S3)、官方实现与本项目锁定的适配代码。

FlashWorld 架构直接使用用户提供的 `FlashWorld_Architecture_v0.10.0.svg`，逐字节复制，不转换或重新绘制；点击图片打开原始 SVG。原有 FlashWorld 自绘流程图与8个模块说明已替换。LucidDreamer 使用用户提供的 `LucidDreamer_Architecture_v0.10.0.svg`，原有自绘图及9个交互模块已移除。

## 可选三维展示

本版没有加入浏览器交互式3D查看器。现有 FlashWorld PLY 约616 MB，LucidDreamer PLY约170 MB，需要进一步完成轻量化与真正高斯渲染器的适配/验收。未把普通点云或预渲染视频冒充交互式三维渲染。网站各视频本身来自三维表示的相机轨迹渲染。

## 文件与维护入口

```text
src/app.js                 # 三个独立轮播、同步比较、观察分析
src/architecture.js        # 两张原始SVG架构图接入与直观理解
src/styles.css             # 响应式和字体
src/fonts/                 # Open Sans与中文字体子集、许可、来源
src/data/site.json         # 通用文案、作者、资源链接
src/data/cases.json        # section字段区分方法、配对、角度
src/data/provenance.json   # 原始实验来源与校验记录
src/data/paired-conditions.json
src/media/                 # 正式展示素材
 tools/site.py             # 检查/构建/子路径预览/限定清理
 tools/refresh_research.py # 只读原实验后重建本轮媒体和配置
 tests/browser_check.py    # 五部分浏览器验收
.github/workflows/pages.yml # 手动触发Pages发布
```

更新单个条目优先手动修改案例配置，见 [CONTENT_GUIDE.md](CONTENT_GUIDE.md)。从当前项目原归档重建全部本轮素材：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
# 仅明确要重建本轮完整案例集合时执行；会重写cases/provenance。
.venv/bin/python -B tools/refresh_research.py
python3 -B tools/site.py build
```

导入程序不修改原实验目录；未接入模型权重、PLY/SPZ或完整环境快照。

## 本地验收

2026-11-03 对构建输出的项目子路径进行 Chromium 验收，9项浏览器测试全部通过（中文版，14.17秒），其中画廊测试逐一播放26条方法结果，范围包括：

- 16个FlashWorld和10个LucidDreamer条目逐一切换、真实解码与自动播放、完整文本对应关系。
- 30°／45°／75°切换；配对视频共同时间轴、播放、暂停和帧差检查。
- `zh-CN`页面语言、中文导航/按钮/场景标题、原始提示词逐条与输入快照核对不变。
- 五部分导航、Open Sans加载、原比例图片、两张原始SVG架构图加载、4级噪声示意。
- 320/390/768/1024/1440px布局、移动菜单、键盘选图、放大与Esc、离开视区暂停、缺失视频重试。

复验：

```bash
.venv/bin/python -m playwright install --with-deps chromium
python3 -B tools/site.py build
.venv/bin/python -B tests/browser_check.py
```

Safari/iOS/Firefox实机、真实触摸手势与线上托管将在本轮部署后核验。发布、更新、回滚和离线导出按 [DEPLOYMENT.md](DEPLOYMENT.md)。本次只修改网站，无训练架构变更，不需要Slurm训练或结果导出操作；原研究结果和环境保持完整。

## 替换模型架构图

两张原图位于项目根目录：`FlashWorld_Architecture_v0.10.0.svg` 与 `LucidDreamer_Architecture_v0.10.0.svg`。更新原图后，从网站目录执行：

```bash
python3 -B tools/import_architecture.py
python3 -B tools/site.py build
```

导入后位于 `src/media/architecture/`，逐字节保留原图并记录来源摘要。FlashWorld保持1500×1840比例，LucidDreamer保持1500×2380比例，点击分别打开原始SVG。旧的自绘架构和交互说明已移除；未改动根目录原图或研究模型。此轮通过SVG解析、SHA-256核对、JavaScript语法检查和静态构建。
