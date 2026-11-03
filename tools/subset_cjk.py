"""Rebuild only the Chinese fallback font; temporary inputs are automatically removed."""
import pathlib,tempfile,urllib.request
from fontTools import subset
ROOT=pathlib.Path(__file__).resolve().parents[1]
text=''.join(p.read_text() for p in (ROOT/'src').rglob('*') if p.suffix in ['.js','.json','.html'])
options=subset.Options();options.flavor='woff2'
with tempfile.TemporaryDirectory(prefix='wm-cjk-') as work:
 source=pathlib.Path(work)/'noto.ttf'
 source.write_bytes(urllib.request.urlopen('https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf').read())
 font=subset.load_font(str(source),options);subsetter=subset.Subsetter(options=options);subsetter.populate(text=''.join(sorted(set(c for c in text if ord(c)>127))));subsetter.subset(font)
 subset.save_font(font,str(ROOT/'src/fonts/NotoSansSC-Research.woff2'),options)
print('Updated src/fonts/NotoSansSC-Research.woff2; rebuild site next.')
