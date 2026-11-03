# 内容与素材维护指南

站点默认语言为 `zh-CN`。请用中文维护案例标题、说明和轨迹名称，保持实验原始 `prompt` 文本不变。`tools/localize_content.py` 负责已有案例的展示文案转换，完整导入脚本会自动调用它。新增中文后执行 `tools/subset_cjk.py` 再构建，以补齐字体字形。


## 五部分配置（2026-11-03）

每个案例新增 `section`：`flashworld`、`luciddreamer`、`comparison` 或 `angles`，分别进入对应展示区。前两部分独立维护选中图片、文本和视频；角度案例在同一个 `results` 数组中放30/45/75度结果。配对案例必须保存真实相机、内参与帧时间协议证据，不能把普通画廊自动当作公平比较。架构模块和教学示意维护在 `src/architecture.js`。

本轮重建素材使用 `tools/refresh_research.py`（依赖同项目原归档，只读原件，重写本轮案例配置）；常规新增只需复制真实媒体、加入配置和来源记录，然后 `python3 -B tools/site.py build`。


修改本站配置与正式媒体后执行构建，不改研究模型，不需要 GPU。所有命令从独立网站目录运行。

## 1. 集中配置与首屏

- `src/data/site.json`：`name`、`authors`、`affiliations`、`links`、`heroCaseId`、`copy`、`evaluation`。
- `src/data/cases.json`：案例及方法结果；一个案例可以有多条预渲染轨迹或不同方法结果。
- `src/data/provenance.json`：本地原实验相对路径、输入和产物摘要、封面提取时间与检查范围。
- `src/media/`：只放本页需要的输入、封面与 MP4。
- `src/fonts/`：WorldScore 同款 Open Sans 本地字体、完整 OFL 许可与字体来源说明；部署时一并保留。

修改 `heroCaseId` 为一个已存在且有 `ready` 结果的案例 ID 即可设置首屏轮播的默认选图。若默认案例属于非精选集合，页面会自动打开完整集合以展示该输入。若该案例尚未就绪，页面自动选第一个可用案例；全部缺失时显示明确空状态。修改 `name` 同步更新导航、浏览器标题与页脚。作者和单位用字符串数组；缺少本项目 Code/Paper 地址时保持空字符串，不用上游链接冒充本项目链接。

正文和交互文案集中在 `copy`（通用控件在 `copy.ui`）。后续增加中文可准备另一份同结构配置并补语言切换；首次 JSON 加载失败提示、无脚本提示、HTML 初始标题仍是 `index.html`/`app.js` 的静态启动回退，改语言时一起调整。

`featured: true` 标记精选案例，`featured: false` 标记完整集合中的其他案例。出现非精选案例时，画廊自动显示 Selected examples / Complete collection 切换；初期全部为精选，不显示无意义的集合切换。首屏、计数与视频播放列表只使用 `ready`；总场景数按 `sourceImageId` 去重，同图不同轨迹不算独立来源图。

## 2. 添加一个新案例

先复制少量真实素材到新目录，避免覆盖现有结果。以下输入的是实际文件路径，不应指向模型权重或完整运行目录。

```bash
(
  set -euo pipefail
  read -r -p '新案例 ID（英文、数字、短横线）：' CASE_ID
  if [[ ! "$CASE_ID" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
    printf '%s\n' 'ID 格式不正确' >&2
    exit 2
  fi
  read -r -p '真实输入图路径：' INPUT_FILE
  read -r -p '真实 MP4 路径：' VIDEO_FILE
  case "$INPUT_FILE" in
    *.png) INPUT_NAME=input.png ;;
    *.jpg|*.jpeg) INPUT_NAME=input.jpg ;;
    *) printf '%s\n' '请提供实际 PNG/JPEG 文件，不要只改后缀' >&2; exit 2 ;;
  esac
  test -f "$INPUT_FILE"
  test -f "$VIDEO_FILE"
  # mkdir 不加 -p：已有案例目录时拒绝继续，防止覆盖。
  mkdir "src/media/$CASE_ID"
  cp -- "$INPUT_FILE" "src/media/$CASE_ID/$INPUT_NAME"
  cp -- "$VIDEO_FILE" "src/media/$CASE_ID/video.mp4"
  sha256sum "$VIDEO_FILE" "src/media/$CASE_ID/video.mp4"
)
```

应结合 manifest 和输入快照核对版本、精确文本、图片、相机设置、分辨率、FPS、时长；不能从文件名推断。构建器通过本地视频 SHA-256 排除复制成不同文件名的相同结果；外部媒体仍需维护者核对是否重复。

新增配置的结构如下（**待补充模板，不是已完成实验**；字段内容必须替换为真实证据后再改状态）：

```json
{
  "id": "new-scene",
  "section": "flashworld",
  "sourceImageId": "source-image-unique-id",
  "title": "New scene",
  "category": "Living spaces",
  "inputImage": "",
  "prompt": "",
  "source": "",
  "featured": false,
  "results": [
    {
      "method": "FlashWorld",
      "version": "",
      "trajectory": "",
      "video": "",
      "poster": "",
      "resolution": [],
      "fps": null,
      "duration": null,
      "status": "pending",
      "notes": "This result has not been verified yet.",
      "comparisonGroup": null,
      "protocolAligned": false,
      "settings": {}
    }
  ]
}
```

向 `cases.json` 数组加入该对象即可扩展页面，不需要改 HTML。视频齐全后填写如 `media/new-scene/video.mp4` 的相对路径或 HTTPS 静态地址。不要填写 `/media/...`、本机绝对路径、Windows 盘符或 `file://`。

对应 `provenance.json` 新增来源记录。至少记录案例 ID、原运行目录、manifest、输入快照、原视频路径、视频/输入/封面 SHA-256、封面提取秒数、原数据图像 ID 和 revision、校验范围。原有三个案例是完整示例，不需要公开整个 manifest 或服务器环境。

### 状态规则

| 状态 | 适用情形 | 页面行为 |
| --- | --- | --- |
| `ready` | 输入图、完整文本、MP4、封面和真实元数据齐全，已检查 | 进入首屏/数量统计；可播放 |
| `pending` | 推理中、尚未导入或证据未补齐 | 明确说明；不请求结果视频或封面 |
| `unavailable` | 结果缺失、损坏或暂不可用 | 明确不可用状态；不请求结果视频或封面 |

已知源文件缺失时改为 `unavailable`。运行时临时网络/解码错误会显示重试，不会偷偷修改维护者的 JSON。输入或文本缺失时不要编造；保持空值并标记待补充。构建器不允许把这样的记录标为 `ready`。

输入图居中轮播参考 [WorldScore](https://haoyi-duan.github.io/WorldScore/) 的图片选择器与下方联动视频结构。点击原图、箭头、圆点或手机水平滑动会同时切换视频、文本与版本。案例 `prompt` 原文以 输入 text 常驻显示在每段视频正上方，包括对比两侧和放大弹窗；只展示真实输入，不截断、不折叠、不改写。缺失时明确标记待补充。当前结果进入可视区时静音自动播放；切换后从头播放；手动暂停会保留，浏览器阻止自动播放时显示手动播放入口。

页面不根据分数自动排序，不提供实时3D推理；轨迹选择切换的是已生成 MP4。无可播放组合时显示状态，不生成空白播放器。当前只有一个方法时不显示独立方法过滤器；一个案例有多个结果时自动出现方法/预渲染轨迹选择器。

## 3. 视频检查与真实封面

普通本地预览不需要额外依赖。仅维护媒体时可以安装本站可选开发依赖：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

利用 CPU 的 FFmpeg 检查整段解码并提取封面，输入实际路径与秒数；不触发科研推理、不裁剪、不插帧：

```bash
read -r -p '网站 MP4 路径（src/media/.../video.mp4）：' MEDIA_VIDEO
read -r -p '对应封面输出路径（src/media/.../poster.jpg）：' MEDIA_POSTER
read -r -p '从实际视频选择封面秒数：' POSTER_SECONDS
.venv/bin/python - "$MEDIA_VIDEO" "$MEDIA_POSTER" "$POSTER_SECONDS" <<'PY'
import pathlib, subprocess, sys
import imageio_ffmpeg
video, poster, seconds = sys.argv[1:]
assert pathlib.Path(video).is_file()
assert not pathlib.Path(poster).exists(), '拒绝覆盖封面；需要替换时先明确处理旧文件'
assert float(seconds) >= 0
ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
subprocess.run([ffmpeg, '-hide_banner', '-i', video, '-f', 'null', '-'], check=True)
subprocess.run([ffmpeg, '-v', 'error', '-ss', seconds, '-i', video,
                '-frames:v', '1', '-q:v', '2', poster], check=True)
assert pathlib.Path(poster).is_file(), '封面时间可能超出视频范围'
PY
sha256sum "$MEDIA_VIDEO" "$MEDIA_POSTER"
```

从解码输出核对真实尺寸/FPS/时长，再浏览器播放完整视频。不要把完整解码成功等同于科学结论。外部视频还需实测 HTTPS、Range 请求、编码、跨域策略和地址稳定性；构建器不会联网下载外部媒体。

本轮全部素材可以用 `tools/refresh_research.py` 重建；它只读取原实验，校验摘要、整段解码并复制 MP4，不发起GPU任务。新增案例后不要重建固定清单以免覆盖手工配置。

## 4. 补齐 LucidDreamer 与启用比较

把真实 LucidDreamer 输出加到**相同输入案例**的 `results` 数组，填写其真实版本/元数据/来源。不要复制 FlashWorld 视频并改方法标签。

同一案例中的至少两个不同方法结果满足 `status: ready`，且共享非空 `comparisonGroup`，才会显示 Comparison 栏目和导航。不同来源输入不能通过填写同一组名合并；同一方法的其他轨迹可以另建分组。

没有足够对齐证据时使用 `protocolAligned: false`。这会显示定性并排结果和两侧手动控制，禁用公共同步控件，说明不能认定公平比较。

启用同步必须同时满足：

- 两条结果均 `protocolAligned: true`。
- `protocol` 中以下字段全部非空且逐项相同。
- 两侧 FPS 相同、配置时长相差小于0.05秒。
- 浏览器中两段视频均加载就绪，实际时长与配置相差小于0.1秒。

```json
{
  "comparisonGroup": "same-input-same-render-protocol",
  "protocolAligned": true,
  "protocol": {
    "cameraPathHash": "实际渲染相机序列规范化后的摘要",
    "intrinsicsHash": "实际渲染内参和视场角序列摘要",
    "sampleTimesHash": "实际渲染帧时间戳序列摘要",
    "coordinateSystem": "有文档说明的共同坐标及尺度约定",
    "inputImageHash": "相同输入图像SHA256",
    "promptHash": "完整文本SHA256"
  }
}
```

以上是字段含义示例，不能将这些说明文字原样当作证据。摘要必须针对完成必要坐标转换后实际送入渲染器的协议；不能把两个方法完全不同的原生相机 JSON 随便写成同一字符串。需要将比对报告保留在项目研究记录，并在案例 `settings` 中说明。

加载失败时公共控件禁用；任一播放器缓冲时双方暂停，双方恢复就绪后继续；公共时间轴会先暂停双方再统一定位。重新开始归零；跨方法比较不独立循环，以免不同解码时机累积偏移。组内多方法取首条结果与第一个不同方法结果，其余对比请分组。

本站同步测试只有界面测试夹具，尚无真实 LucidDreamer 对比结论。

## 5. 定量评测与真实失败案例

当前五部分只展示真实视频、配对帧和方法解释，没有定量评测区。`site.json` 的 `evaluation` 保留为空；后续有完整评测集合、独立样本数、协议、方向明确的指标和来源报告时，再实现对应表格。不填写演示分数，不把当前案例数当作独立场景数。

本次 room40 的真实画面及观察位于 `src/app.js` 的 `comparisonAnalysis()`；增加观察必须引用具体帧。架构模块的机制解释位于 `src/architecture.js`，要保持“实际观察”和“尚未经消融验证的解释”的区别。没有本项目出版信息时不生成 BibTeX。

## 6. 每次更新验收与清理

```bash
python3 -B tools/site.py check
python3 -B tools/site.py build
python3 -B tools/site.py preview
```

检查首屏、所有新视频、切换后的文本和版本、手机布局、Tab/Esc、错误状态。需要回归测试时执行：

```bash
.venv/bin/python -B tests/browser_check.py
```

删除本站不再被配置引用的废弃素材前，先检查引用，不自动删除科研原件。示例仅列出引用供检查：

```bash
python3 - <<'PY'
import json
from pathlib import Path
for c in json.loads(Path('src/data/cases.json').read_text()):
    print(c['id'], c['inputImage'])
    for r in c['results']:
        print(' ', r['status'], r['video'], r['poster'])
PY
```

如果只需清理构建和 Python 缓存：

```bash
python3 -B tools/site.py clean
python3 -B tools/site.py build
```

部署、实时 Actions 日志和离线导出命令见 [DEPLOYMENT.md](DEPLOYMENT.md)。无需训练日志或 Slurm 指令，因为此阶段没有修改科研架构或发起训练。

## 模型架构图素材

两张图直接使用项目根目录的 `FlashWorld_Architecture_v0.10.0.svg` 与 `LucidDreamer_Architecture_v0.10.0.svg`。替换原图后运行：

```bash
python3 -B tools/import_architecture.py
python3 -B tools/site.py build
```

该导入工具仅使用Python标准库，将两张SVG原样复制到 `src/media/architecture/` 并记录摘要。页面保持各自原始比例，点击可以打开原图；两种模型的旧自绘交互图均已替换。不涉及GPU训练或Slurm任务。
