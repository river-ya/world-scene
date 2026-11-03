# Open Sans 字体来源

本站使用与 [WorldScore](https://haoyi-duan.github.io/WorldScore/) 相同的 Open Sans 静态字体文件。本地托管，无需访问外部字体服务。

原站定义：[open-sans.css](https://haoyi-duan.github.io/WorldScore/assets/fonts/open-sans.css)。正文 Regular 400、Medium 500、SemiBold 600、标题 Bold 700。没有修改字体文件。

Copyright 2020 The Open Sans Project Authors (https://github.com/googlefonts/opensans)。使用 SIL Open Font License 1.1，完整许可保留为 [OFL.txt](OFL.txt)，从 [Google Fonts 官方仓库](https://github.com/google/fonts/blob/main/ofl/opensans/OFL.txt) 获取，版权信息与字体内嵌 name table 一致。

| 文件及来源 | SHA-256 |
| --- | --- |
| [OpenSans-Bold.ttf](https://haoyi-duan.github.io/WorldScore/assets/fonts/OpenSans-Bold.ttf) | `bc73c45e5810a0971ebeaef4eb6c35dec84607dbe02da6757f9f43d958b6da5f` |
| [OpenSans-Medium.ttf](https://haoyi-duan.github.io/WorldScore/assets/fonts/OpenSans-Medium.ttf) | `2ab15629424ace86d429dbc0e5a7beb30d2af3db998a2b03a71601ee6965c334` |
| [OpenSans-Regular.ttf](https://haoyi-duan.github.io/WorldScore/assets/fonts/OpenSans-Regular.ttf) | `6530480277da62efde047eb26e78a7e532d1cfaeec91603e68d63876b9669f0d` |
| [OpenSans-SemiBold.ttf](https://haoyi-duan.github.io/WorldScore/assets/fonts/OpenSans-SemiBold.ttf) | `e603135cc3b1200c7260b34f37f9cb1f2178a42b363037e26a1e18276ab78bf0` |

## 中文补充字体

为架构讲解提供 Noto Sans SC 的字形子集，不替换英文 Open Sans。源字体：[Google Fonts 官方 NotoSansSC 可变字体](https://github.com/google/fonts/blob/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf)，按网站当前中文字符以 fontTools 子集化为 WOFF2。许可见 [NOTO-OFL.txt](NOTO-OFL.txt)。添加新中文时需要重新生成子集或使用完整字体；系统中文字体仍作后备。

重新生成（从网站根目录，需安装 requirements-dev.txt）：

```bash
.venv/bin/python -B tools/subset_cjk.py
python3 -B tools/site.py build
```
