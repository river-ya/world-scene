"""Acceptance for five real-data chapters; no synthetic scientific results are saved."""
import json,os,pathlib,subprocess,sys,time,unittest,urllib.request
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
class BrowserChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.server=subprocess.Popen([sys.executable,'-B',str(ROOT/'tools/site.py'),'preview','--port','8765'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  for _ in range(100):
   try:urllib.request.urlopen('http://127.0.0.1:8765/world-scene/');break
   except OSError:time.sleep(.1)
  cls.p=sync_playwright().start();kwargs={'headless':True}
  if os.getenv('BROWSER_EXECUTABLE'):kwargs['executable_path']=os.environ['BROWSER_EXECUTABLE']
  cls.browser=cls.p.chromium.launch(**kwargs);cls.cases=json.loads((ROOT/'src/data/cases.json').read_text())
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.p.stop();cls.server.terminate();cls.server.wait(timeout=10)
 def setUp(self):
  self.context=self.browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce');self.page=self.context.new_page();self.errors=[];self.requests=[]
  self.page.on('pageerror',lambda e:self.errors.append(str(e)));self.page.on('request',lambda r:self.requests.append(r.url));self.page.set_default_timeout(15000)
  self.page.goto('http://127.0.0.1:8765/world-scene/');self.page.wait_for_selector('#flashworld video')
 def tearDown(self):self.context.close();self.assertEqual(self.errors,[])
 def test_chapters_and_fonts(self):
  self.assertEqual(self.page.locator('nav a').count(),5)
  for id in ['flashworld','luciddreamer','comparison','angles','architecture']:self.assertEqual(self.page.locator('#'+id).count(),1)
  self.page.evaluate('document.fonts.ready');self.assertIn('Open Sans',self.page.locator('h1').evaluate('(e)=>getComputedStyle(e).fontFamily'))
  self.assertEqual(self.page.locator('#flashworld .thumb').count(),16);self.assertEqual(self.page.locator('#luciddreamer .thumb').count(),10)
 def test_chinese_locale_and_original_prompts(self):
  self.assertEqual(self.page.locator('html').get_attribute('lang'),'zh-CN')
  self.assertEqual(self.page.locator('nav a').all_inner_texts(),['FlashWorld','LucidDreamer','方法对比','转动角度','模型架构'])
  self.assertEqual(self.page.locator('#flashworld .prompt-label').inner_text(),'输入 text')
  self.page.evaluate('document.fonts.ready')
  self.assertTrue(self.page.evaluate("""document.fonts.check('400 16px \"Noto Sans SC\"')"""))
  provenance=json.loads((ROOT/'src/data/provenance.json').read_text())
  by_id={p['id']:p for p in provenance}
  for c in self.cases:
   for r in c['results']:
    slug=r['video'].split('/')[1];source=by_id[slug]
    snapshot=json.loads((ROOT.parent/source['inputSnapshot']).read_text())
    self.assertEqual(c['prompt'],snapshot['text_prompt'])
 def test_all_gallery_selections(self):
  for section in ['flashworld','luciddreamer']:
   for c in [c for c in self.cases if c['section']==section]:
    self.page.locator('#'+section).get_by_role('button',name='选择输入图像: '+c['title'],exact=True).click()
    self.page.locator('#'+section+' video').scroll_into_view_if_needed()
    self.page.wait_for_function('(id)=>{let v=document.querySelector(`#${id} video`);return v.readyState>=3 && !v.paused && v.currentTime>0.05}',arg=section)
    self.assertEqual(self.page.locator('#'+section+' .prompt-text').inner_text(),c['prompt'])
    self.assertIn(c['results'][0]['video'],self.page.locator('#'+section+' video').get_attribute('src'))
    self.assertEqual(self.page.locator('#'+section+' video').evaluate('(v)=>[v.videoWidth,v.videoHeight]'),[704,480])
 def test_angle_switch(self):
  c=next(c for c in self.cases if c['section']=='angles')
  for i,r in enumerate(c['results']):
   self.page.locator('#angles select').select_option(str(i));self.page.locator('#angles video').scroll_into_view_if_needed()
   self.page.wait_for_function('()=>document.querySelector("#angles video").currentTime>0.1')
   self.assertIn(r['video'],self.page.locator('#angles video').get_attribute('src'));self.assertEqual(self.page.locator('#angles .prompt-text').inner_text(),c['prompt'])
 def test_pair_sync_and_frames(self):
  self.page.locator('#comparison .sync-controls').scroll_into_view_if_needed()
  self.page.locator('#comparison').get_by_role('button',name='同步播放',exact=True).click()
  self.page.wait_for_function('()=>[...document.querySelectorAll("#comparison video")].every(v=>!v.paused && v.currentTime>0.2)')
  times=self.page.locator('#comparison video').evaluate_all('(vs)=>vs.map(v=>v.currentTime)');self.assertLess(abs(times[0]-times[1]),.2)
  self.page.locator('#comparison').get_by_role('button',name='同步暂停',exact=True).click();self.assertTrue(self.page.locator('#comparison video').evaluate_all('(vs)=>vs.every(v=>v.paused)'))
  self.page.locator('#comparison input').fill('12');self.page.wait_for_timeout(250)
  self.assertTrue(self.page.locator('#comparison video').evaluate_all('(vs)=>vs.every(v=>Math.abs(v.currentTime-12)<.2)'))
  self.assertEqual(self.page.locator('.evidence-grid img').count(),4)
 def test_architecture_images(self):
  self.assertEqual(self.page.locator('.architecture-node').count(),0)
  for slug,height in [('flashworld','1840'),('luciddreamer','2380')]:
   image=self.page.locator(f'.{slug}-architecture img');image.scroll_into_view_if_needed()
   self.assertEqual(image.get_attribute('src'),f'media/architecture/{slug}-v0.10.0.svg')
   self.assertEqual(image.get_attribute('height'),height)
   self.page.wait_for_function('(slug)=>document.querySelector(`.${slug}-architecture img`).naturalWidth>0',arg=slug)
  self.assertEqual(self.page.locator('.teaching-demo h3').first.inner_text(),'直观理解')
  self.page.wait_for_function('document.querySelectorAll(".noise-row canvas").length===4')
 def test_mobile_and_keyboard(self):
  for width in [1440,1024,768,390,320]:
   self.page.set_viewport_size({'width':width,'height':844});self.assertFalse(self.page.evaluate('document.documentElement.scrollWidth>innerWidth'),str(width))
  self.page.locator('#menu').click();self.page.locator('nav').get_by_role('link',name='LucidDreamer',exact=True).click();self.assertEqual(self.page.locator('#menu').get_attribute('aria-expanded'),'false')
  self.page.locator('#luciddreamer .thumb[aria-pressed=true]').focus();self.page.keyboard.press('ArrowRight');self.assertEqual(self.page.locator('#luciddreamer h3').inner_text(),'音响房间')
 def test_modal_and_pause(self):
  self.page.locator('#flashworld').get_by_role('button',name='放大查看 ↗',exact=True).click();self.assertTrue(self.page.locator('dialog').is_visible());self.assertTrue(self.page.locator('dialog .prompt-text').is_visible())
  self.page.keyboard.press('Escape');self.assertFalse(self.page.locator('dialog').is_visible())
  self.page.locator('#flashworld video').scroll_into_view_if_needed();self.page.locator('#flashworld video').evaluate('(v)=>v.play()')
  self.page.locator('#architecture').scroll_into_view_if_needed();self.page.wait_for_function('document.querySelector("#flashworld video").paused')
 def test_lazy_and_error(self):
  self.assertFalse(any('/media/lucid-1/video.mp4' in r for r in self.requests))
  self.page.route('**/media/lucid-1/video.mp4',lambda r:r.fulfill(status=404,body='missing'))
  self.page.locator('#luciddreamer').get_by_role('button',name='选择输入图像: 音响房间',exact=True).click();self.page.locator('#luciddreamer .player').scroll_into_view_if_needed();self.page.locator('#luciddreamer').get_by_role('button',name='重试',exact=True).wait_for()
if __name__=='__main__':unittest.main(verbosity=2)
