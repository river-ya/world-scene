"""Translate display metadata; preserve original experimental prompts and media paths."""
import json,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parents[1]
TITLES={'Living room':'客厅','Sound studio':'音响房间','Modern kitchen':'现代厨房','Living & dining':'客餐厅','Abandoned hallway':'废弃走廊','Historic library':'历史图书馆','Modern office':'现代办公室','Second kitchen':'第二间厨房','Living room · camera variant':'客厅 · 相机轨迹变体','Sound studio · text variant':'音响房间 · 文本变体','Living room · right turn':'客厅 · 向右转动','Sound studio · text + camera variant':'音响房间 · 文本与相机变体','Living & dining · angle sweep':'客餐厅 · 转动角度实验','Living room · matched left 40°':'客厅 · 同条件左转40°'}
def localize_cases(cases):
 for c in cases:
  original=c['title'];base=original.removesuffix(' · wide view');c['title']=TITLES.get(base,base)+(' · 大视角' if original.endswith(' · wide view') else '')
  c['category']={'Living spaces':'起居空间','Studios':'音响房间','Kitchens':'厨房'}.get(c['category'],c['category'])
  c['source']={'FlashWorld example 3':'FlashWorld 官方示例3','FlashWorld example 5':'FlashWorld 官方示例5','WorldScore · indoor dev subset':'WorldScore 室内开发子集','Archived official/example input':'归档的官方示例输入'}.get(c.get('source'),c.get('source'))
  for r in c['results']:
   tr=r['trajectory'];tr={'official-3':'官方示例3相机轨迹','official-5':'官方示例5相机轨迹','room_short':'客厅短轨迹','studio':'音响房间轨迹','studio_mirrored':'音响房间镜像轨迹','official camera template':'官方相机模板','Left 40° · fixed center':'固定中心左转40°'}.get(tr,tr)
   tr=re.sub(r'^Left (\d+)°$',r'左转\1°',tr)
   if tr.endswith('° yaw'):
    value=float(tr.removesuffix('° yaw'));tr=('左转' if value>=0 else '右转')+f'{abs(value):g}°'
   r['trajectory']=tr
   if r['notes'].isascii():r['notes']='真实归档结果；保留原实验版本和相机条件。本展示用于定性观察，不代表整体性能评测。'
 return cases
if __name__=='__main__':
 p=ROOT/'src/data/cases.json';cases=json.loads(p.read_text());prompts=[c['prompt'] for c in cases];localize_cases(cases);assert prompts==[c['prompt'] for c in cases];p.write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n')
