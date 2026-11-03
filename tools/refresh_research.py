"""Import verified local research exports; originals are read only. No GPU work."""
import base64,hashlib,json,pathlib,re,shutil,subprocess
from PIL import Image
import imageio_ffmpeg
ROOT=pathlib.Path(__file__).resolve().parents[1];PROJECT=ROOT.parent;DATA=ROOT/'src/data';MEDIA=ROOT/'src/media'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
ff=imageio_ffmpeg.get_ffmpeg_exe();cases=read(DATA/'cases.json');provenance=read(DATA/'provenance.json')
cases=[c for c in cases if c['id'] in ['room','studio','kitchen']]
provenance=[p for p in provenance if p['id'] in ['room','studio','kitchen']]
for c in cases:
 c['section']='flashworld'
 c['sourceImageId']={'room':'official-3','studio':'official-5','kitchen':'ws-indoor-000'}[c['id']]
seen={r['video'] for c in cases for r in c['results']}
def add(run,slug,method,section,title,video=None,snapshot=None,trajectory=None):
 m=read(run/'manifest.json');assert m['status']=='complete',run
 snapshot=snapshot or next(iter((run/'portable_inputs').glob('*.json')),None) or run/'inputs/flashworld.json'
 x=read(snapshot);video=video or next((run/'outputs').rglob('video.mp4'))
 rel=str(video.relative_to(run));entry=m['artifacts'].get(rel) or m['artifacts'].get(video.name)
 expected=entry.get('sha256') if isinstance(entry,dict) else entry
 assert expected and sha(video)==expected,(video,'digest mismatch')
 out=MEDIA/slug;out.mkdir(exist_ok=True)
 encoded=x['image_prompt'];ext='jpg' if encoded.startswith('data:image/jpeg') else 'png';image=out/f'input.{ext}';image.write_bytes(base64.b64decode(encoded.split(',',1)[1]))
 with Image.open(image) as im:im.verify()
 shutil.copyfile(video,out/'video.mp4')
 result=subprocess.run([ff,'-hide_banner','-i',str(video),'-f','null','-'],capture_output=True,text=True,check=True)
 s=result.stderr;wh=re.search(r'Video:.*? (\d{2,5})x(\d{2,5})',s);fps=float(re.search(r'(\d+(?:\.\d+)?) fps',s)[1]);dur=re.search(r'Duration: (\d+):(\d+):([\d.]+)',s);duration=int(dur[1])*3600+int(dur[2])*60+float(dur[3])
 anchor=float(x.get('image_index',0));subprocess.run([ff,'-v','error','-y','-ss',str(anchor),'-i',str(video),'-frames:v','1','-q:v','2',str(out/'poster.jpg')],check=True)
 profile=x.get('_angles') or x.get('_wideview') or x.get('_lucid_camera') or x.get('_gallery') or {}
 tr=trajectory or (str(profile.get('signed_yaw_deg',profile.get('max_yaw_deg','')))+'° yaw' if 'signed_yaw_deg' in profile or 'max_yaw_deg' in profile else profile.get('camera_profile','official camera template'))
 source=x.get('_showcase',{}).get('distinct_input_id') or profile.get('scene') or slug
 if section=='luciddreamer':source=['official-3','official-5','ws-indoor-000','ws-indoor-001','ws-indoor-002','ws-indoor-003','ws-indoor-004','ws-indoor-005','official-3','official-5'][int(slug.split('-')[1])]
 if section=='comparison':source='official-3'
 if 'room' in str(source) or str(source)=='official-3':source='official-3'
 if 'studio' in str(source) or str(source)=='official-5':source='official-5'
 r={'method':method,'version':'v'+m['version'],'trajectory':tr,'video':f'media/{slug}/video.mp4','poster':f'media/{slug}/poster.jpg','resolution':[int(wh[1]),int(wh[2])],'fps':fps,'duration':duration,'status':'ready','notes':'Archived result. Camera protocol and experiment version are preserved; this is a qualitative development example.','comparisonGroup':None,'protocolAligned':False,'settings':{'seed':m.get('seed',0),'sampledCameras':len(x.get('cameras',[])),'inputAnchorIndex':x.get('image_index',0),'cameraProfile':profile,'metricScaleAlignment':m.get('metric_scale_alignment','not established')}}
 c={'id':slug,'section':section,'sourceImageId':source,'title':title,'category':method,'inputImage':f'media/{slug}/input.{ext}','prompt':x['text_prompt'],'source':x.get('_showcase',{}).get('source_image','Archived official/example input'),'featured':True,'results':[r]}
 cases.append(c);provenance.append({'id':slug,'sourceRun':str(run.relative_to(PROJECT)),'inputSnapshot':str(snapshot.relative_to(PROJECT)),'inputSnapshotSha256':sha(snapshot),'videoSource':str(video.relative_to(PROJECT)),'videoSha256':sha(video),'inputSha256':sha(image),'posterSha256':sha(out/'poster.jpg'),'posterSeconds':anchor,'mediaCheck':'manifest SHA256 + full CPU decode + input verification; unchanged MP4','manifestVisualAcceptance':m.get('visual_acceptance','not recorded')})
 print(slug,method,r['resolution'],duration,flush=True);return c
names={3:'Living & dining',4:'Abandoned hallway',5:'Historic library',6:'Modern office',7:'Second kitchen',8:'Living room · camera variant',9:'Sound studio · text variant'}
for run in sorted((PROJECT/'实验结果/world_scene-v0.6.0-varied-71013').glob('gallery-*')):
 i=int(run.name.split('-')[1]);add(run,'flash-varied-'+str(i),'FlashWorld','flashworld',names[i])
for run in sorted((PROJECT/'实验结果/world_scene-v0.9.0-wideview-71820-main').glob('wideview-*')):
 i=int(run.name.split('-')[1]);add(run,'flash-wide-'+str(i),'FlashWorld','flashworld',names[i]+' · wide view')
lnames=['Living room','Sound studio','Modern kitchen','Living & dining','Abandoned hallway','Historic library','Modern office','Second kitchen','Living room · right turn','Sound studio · text + camera variant']
for run in sorted((PROJECT/'实验结果/world_scene-v0.10.0-lucid-all-final74326').glob('lucid-*')):
 i=int(run.name.split('-')[1]);add(run,'lucid-'+str(i),'LucidDreamer','luciddreamer',lnames[i])
anglecases=[]
for run in sorted((PROJECT/'实验结果/world_scene-v0.8.0-angles-71446-main').glob('angles-*')):
 angle=int(run.name.split('-')[3]);anglecases.append(add(run,'angle-'+str(angle),'FlashWorld','angles','Living & dining · angle sweep',trajectory=f'Left {angle}°'))
anglecases.sort(key=lambda c:int(c['id'].split('-')[1]));ac=anglecases[0];ac['id']='angle-sweep';ac['results']=[c['results'][0] for c in anglecases];cases=[c for c in cases if c not in anglecases]+[ac]
# Keep separate provenance IDs for each angle's media.
base=PROJECT/'实验结果/paired-room40-74470';cond=read(base/'comparison/conditions.json')
f=add(base/'FlashWorld/flash-room40-74470','paired-flash','FlashWorld','comparison','Living room · matched left 40°',snapshot=base/'FlashWorld/flash-room40-74470/inputs/room-left40.json',trajectory='Left 40° · fixed center')
lrun=base/'LucidDreamer/common-white-render'
l=add(lrun,'paired-lucid','LucidDreamer','comparison',f['title'],video=lrun/'video.mp4',snapshot=base/'LucidDreamer/lucid-00-74280-0/inputs/flashworld.json',trajectory='Left 40° · fixed center')
protocol=read(base/'LucidDreamer/lucid-00-74280-0/inputs/protocol.json')
assert read(base/'FlashWorld/flash-room40-74470/inputs/room-left40.json')==read(base/'LucidDreamer/lucid-00-74280-0/inputs/flashworld.json')
assert cond['image_pixel_match'] and cond['actual_normalized_generation_and_dense_camera_match'] and cond['intrinsics_match']
for c in [f,l]:
 r=c['results'][0];r.update(comparisonGroup='paired-room40-74470',protocolAligned=True,protocol={'cameraPathHash':digest(protocol['render_cameras']),'intrinsicsHash':digest([{k:v for k,v in a.items() if k in ['fx','fy','cx','cy']} for a in protocol['render_cameras']]),'sampleTimesHash':digest([i/15 for i in range(346)]),'coordinateSystem':protocol['coordinate_system'],'inputImageHash':sha(MEDIA/'paired-flash/input.png'),'promptHash':digest(f['prompt'])})
 r['settings']['comparisonConditions']={k:cond[k] for k in ['motion','metric_scale_alignment','common_render_background_rgb','model_specific_differences']}
 r['duration']=346/15
f['id']='paired-room40';f['results']=[l['results'][0],f['results'][0]];cases.remove(l)
shutil.copyfile(base/'comparison/conditions.json',DATA/'paired-conditions.json')
frames=MEDIA/'comparison';frames.mkdir(exist_ok=True)
for n in ['000','150','300','345']:shutil.copyfile(base/f'comparison/frame-{n}.png',frames/f'frame-{n}.png')
from localize_content import localize_cases
localize_cases(cases)
(DATA/'cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n');(DATA/'provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n')
print('TOTAL',len(cases),'cases',sum(len(c['results']) for c in cases),'videos')
