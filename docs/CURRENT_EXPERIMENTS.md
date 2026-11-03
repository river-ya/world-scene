# 当前实验与 LucidDreamer 多样相机

公开 v0.10.1 对齐内部 v0.10.0。模型和权重不变，十例使用固定中心、相对输入水平转向、输入锚点 0。共八张源图，变体不算独立场景。

| 索引 | 场景 | 转向 |
| --- | --- | --- |
| 0 | room | 左 40° |
| 1 | studio | 右 50° |
| 2 | 第一厨房 | 左 45° |
| 3 | 客厅/餐区 | 左 65° |
| 4 | 走廊 | 左 35° |
| 5 | 图书馆 | 右 60° |
| 6 | 办公室 | 右 55° |
| 7 | 另一厨房 | 左 48° |
| 8 | room 相机变体 | 右 58° |
| 9 | studio 文本与相机变体 | 左 52° |

这些角度是项目开发设置，不是论文最优值。索引 9 改变文本和相机，不是纯文本消融。跨模型对照使用 inputs/flashworld.json，不混用早期 angles/wideview 轨迹。

## 导入、环境与预检

完整源码上传、导入、环境安装和配置见 [SLURM.md](SLURM.md)。两模型使用独立环境，已有验证环境可复用。新公开版本改变项目锁摘要，等旧 FlashWorld 任务结束后再完整校验资产回执。

~~~bash
source slurm/lucid/config.sh
python3 -B tools/lucid_assets.py source-check
"$LUCID_PYTHON" -B tools/lucid_assets.py verify --root "$LUCID_ASSETS"
"$LUCID_PYTHON" -B tools/lucid.py preflight --array '0-9%1'
~~~

缺失权重使用 lucid_assets.py download。HF_ENDPOINT 仅影响 Hugging Face，不改变 ZoeDepth 的 GitHub URL。保留下载分片和首次来源记录，不手工伪造回执。

## 首次 GPU 检查与单例

~~~bash
source slurm/lucid/config.sh
LUCID_ARRAY='1%1' LUCID_DEPENDENCY= bash slurm/lucid/submit.sh check
LUCID_JOB=$(cat "$LUCID_STATE/check.jobid")
bash slurm/lucid/logs.sh "$LUCID_JOB"
~~~

检查成功后先跑索引 1、导出并视觉验收，再跑其他案例：

~~~bash
LUCID_ARRAY='1%1' LUCID_DEPENDENCY= bash slurm/lucid/submit.sh run
LUCID_JOB=$(cat "$LUCID_STATE/run.jobid")
bash slurm/lucid/logs.sh "$LUCID_JOB"
~~~

## 并行和 QOS

数组每个元素申请一张 GPU。%4 表示最多四个同时运行，排队元素仍计入提交上限。查询自己的额度：

~~~bash
squeue -r -u "$USER"
sacctmgr show qos where Name="$LUCID_QOS" format=Name,MaxSubmitJobsPU,MaxJobsPU,MaxTRESPU
~~~

例如有效额度是最多提交 8 个、运行 4 个，且没有其他占用，可先提交 0,2-8%4，释放额度后再提交 9%1。不能一次提交九个并误以为 %4 限制了提交总数。

~~~bash
LUCID_ARRAY='0,2-8%4' LUCID_DEPENDENCY= bash slurm/lucid/submit.sh run
# 上一批结束后再执行：
# LUCID_ARRAY='9%1' LUCID_DEPENDENCY= bash slurm/lucid/submit.sh run
~~~

技术完成需结合 sacct COMPLETED / 0:0、manifest complete 和输出摘要，不能只看队列消失。

## 导出和清理

根据 case-N.jobid 定位实际结果，支持跨批次及重试：

~~~bash
source slurm/lucid/config.sh
LABEL=$(date +%Y%m%d-%H%M%S)
"$LUCID_PYTHON" -B tools/lucid_export.py --indices 0 1 2 3 4 5 6 7 8 9 \
  --output "$LUCID_DATA_ROOT/exports/lucid-varied-$LABEL.tar.gz"
~~~

本地下载与解压模式见 [同条件指南](PAIRED_COMPARISON.md)，将文件名与数据根改成自己的值。临时任务目录清理也见该指南，保留正式资产、输入和失败记录。
