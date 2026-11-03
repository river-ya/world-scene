import { architectureSection } from './architecture.js';
const $ = (s, root = document) => root.querySelector(s);
const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };
const append = (parent, ...children) => { parent.append(...children.filter(Boolean)); return parent; };
const button = (label, fn, cls = 'button') => { const b = el('button', cls, label); b.type = 'button'; b.addEventListener('click', fn); return b; };
const asset = value => { if (!value) return ''; const u = new URL(value, new URL('./', location.href)); if (!['http:', 'https:'].includes(u.protocol)) return ''; return u.href; };
const link = (label, url, cls) => { const a = el('a', cls, label); a.href = asset(url); if (new URL(a.href).origin !== location.origin) { a.target = '_blank'; a.rel = 'noopener noreferrer'; } return a; };
let site, cases, t;
const players = new Set();
const ready = r => r.status === 'ready';
const readyCases = () => cases.filter(c => c.results.some(ready));
function photo(src, alt, eager = false) {
  const frame = el('div', 'frame');
  if (!asset(src)) return append(frame, el('div', 'video-error', t.missingInput));
  const img = el('img'); img.alt = alt; img.loading = eager ? 'eager' : 'lazy'; img.decoding = 'async'; img.src = asset(src);
  img.addEventListener('error', () => { img.remove(); frame.append(el('div', 'video-error', t.missingInput)); }, { once: true });
  return append(frame, img);
}
function stopAll(except = []) { for (const p of players) if (!except.includes(p)) p.pauseSystem(); }
function videoPlayer(result, title, { eager = false, expand = true, exclusive = true, auto = false, inputPrompt = '' } = {}) {
  const root = el('div', 'player');
  if (!ready(result)) { root.append(el('div', 'video-error', result.status === 'pending' ? t.pending : t.unavailable)); return { root, dispose() {} }; }
  const frame = el('div', 'frame'), video = el('video');
  video.muted = true; video.defaultMuted = true; video.loop = true; video.playsInline = true; video.controls = true; video.preload = 'metadata';
  video.setAttribute('aria-label', `${title} — ${result.method}`); video.width = result.resolution[0]; video.height = result.resolution[1]; video.style.aspectRatio = `${result.resolution[0]}/${result.resolution[1]}`;
  if (asset(result.poster)) video.poster = asset(result.poster);
  const status = el('p', 'sr-only'); status.setAttribute('role', 'status');
  let loaded = false, failed = false, disposed = false, visible = false, userPaused = false, systemPaused = false, autoBlocked = false, playPending = false;
  const load = () => { if (!loaded && !disposed) { loaded = true; video.src = asset(result.video); video.load(); } };
  const pauseSystem = () => { systemPaused = true; video.pause(); };
  const play = async (automatic = false) => {
    if (disposed || playPending) return;
    load(); playPending = true; systemPaused = false;
    if (!automatic) { userPaused = false; autoBlocked = false; }
    try { if (exclusive) stopAll([api]); await video.play(); if (disposed || document.hidden || (automatic && !visible)) pauseSystem(); }
    catch (error) { if (!disposed && error.name !== 'AbortError') { autoBlocked = automatic; status.textContent = failed ? t.failed : automatic ? t.autoplayBlocked : t.play; } }
    finally { playPending = false; }
  };
  const tryAuto = () => { if (auto && visible && !userPaused && !autoBlocked && !failed && !document.hidden && (!$('#viewer').open || $('#viewer').contains(root)) && video.paused) play(true); };
  const toggle = button(t.play, () => { if (video.paused) play(); else { userPaused = true; video.pause(); } });
  const controls = append(el('div', 'media-actions'), toggle);
  const error = append(el('div', 'video-error'), el('span', '', t.failed), button(t.retry, () => { failed = false; autoBlocked = false; error.hidden = true; video.hidden = false; toggle.disabled = false; loaded = false; load(); })); error.hidden = true;
  video.addEventListener('play', () => { if (disposed) { pauseSystem(); return; } if (exclusive) stopAll([api]); userPaused = false; toggle.textContent = t.pause; });
  video.addEventListener('pause', () => { if (!video.paused) return; if (visible && !systemPaused && !failed) userPaused = true; toggle.textContent = t.play; });
  video.addEventListener('waiting', () => { status.textContent = t.buffering; });
  video.addEventListener('canplay', () => { if (!autoBlocked) status.textContent = t.ready; tryAuto(); });
  video.addEventListener('playing', () => { status.textContent = t.ready; });
  video.addEventListener('error', () => { failed = true; video.pause(); video.hidden = true; error.hidden = false; toggle.disabled = true; status.textContent = t.failed; });
  const observer = new IntersectionObserver(entries => { for (const e of entries) if (e.isIntersecting) load(); }, { rootMargin: '80px' });
  const visibility = new IntersectionObserver(entries => { for (const e of entries) { visible = e.isIntersecting; if (visible) tryAuto(); else pauseSystem(); } });
  append(root, append(frame, video, error), controls, status);
  const api = { root, video, load, play, pauseSystem, tryAuto, dispose() { disposed = true; observer.disconnect(); visibility.disconnect(); pauseSystem(); video.removeAttribute('src'); video.load(); players.delete(api); } };
  players.add(api); observer.observe(root); visibility.observe(frame); if (eager) load();
  if (expand) controls.append(button(t.expand, () => openViewer(result, title, inputPrompt)));
  return api;
}
let dialogPlayer, dialogOpener;
function openViewer(result, title, inputPrompt) {
  dialogOpener = document.activeElement; stopAll(); $('#viewer-title').textContent = `${title} · ${result.method}`;
  dialogPlayer = videoPlayer(result, title, { eager: true, expand: false, auto: true }); $('#viewer-body').replaceChildren(promptBlock(inputPrompt), dialogPlayer.root);
  $('#viewer').showModal(); $('#close-viewer').focus();
}
$('#close-viewer').onclick = () => $('#viewer').close();
$('#viewer').addEventListener('close', () => { dialogPlayer?.dispose(); $('#viewer-body').replaceChildren(); dialogOpener?.focus(); });
$('#viewer').addEventListener('keydown', event => {
  if (event.key !== 'Tab') return;
  const focusable = [...$('#viewer').querySelectorAll('button, video[controls], a[href], input, select, [tabindex="0"]')].filter(n => !n.disabled && n.getClientRects().length);
  const first = focusable[0], last = focusable.at(-1);
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
});
document.addEventListener('visibilitychange', () => { if (document.hidden) stopAll(); else for (const p of players) p.tryAuto(); });
$('#menu').onclick = () => { const open = $('#menu').getAttribute('aria-expanded') !== 'true'; $('#menu').setAttribute('aria-expanded', String(open)); $('#navigation').classList.toggle('open', open); };
$('#navigation').addEventListener('click', e => { if (e.target.closest('a')) { $('#menu').setAttribute('aria-expanded', 'false'); $('#navigation').classList.remove('open'); } });
function section(id, index, heading) { const s = el('section', 'section'); s.id = id; append(s, el('div', 'kicker', index), el('h2', '', heading)); return s; }
function promptBlock(prompt) { return append(el('div', 'prompt-input'), el('div', 'prompt-label', t.prompt), el('p', 'prompt-text', prompt || t.missingPrompt)); }
function resultFigure(r, c, options) { const p = videoPlayer(r, c.title, { ...options, inputPrompt: c.prompt }); return { figure: append(el('figure'), options?.exclusive === false ? el('h4', 'result-method', r.method) : null, promptBlock(c.prompt), p.root), player: p }; }
function hero() {
  const s = el('section', 'hero');
  append(s, el('div', 'eyebrow', t.eyebrow), el('h1', '', site.name), el('p', 'subtitle', t.subtitle));
  if (site.authors.length) s.append(el('p', 'lede', site.authors.join(' · ')));
  if (site.affiliations.length) s.append(el('p', 'lede', site.affiliations.join(' · ')));
  const actions = el('div', 'actions');
  for (const [label, url] of Object.entries(site.links)) if (url) actions.append(link(label === 'code' ? t.ui.code : t.ui.paper, url, 'button'));
  if (actions.children.length) s.append(actions);
  return s;
}
function gallery({id, title, description, dataset, ordinal}) {
  const cases = dataset;
  const readyCases = () => cases.filter(c => c.results.some(ready));
  const s = el('section', 'showcase research-chapter'); s.id = id;
  s.append(el('div', 'chapter-number', ordinal));
  s.append(el('h2', 'selector-title', title));
  let current = readyCases().find(c => c.id === site.heroCaseId) || readyCases()[0] || cases[0];
  let currentPlayer, collection = current?.featured === false ? 'all' : 'featured', selectedCategory = '*', visibleCases = [], scrollTimer;
  const collectionControls = el('div', 'filters');
  const filters = el('div', 'filters'); filters.setAttribute('aria-label', t.ui.sceneCategories);
  const stage = el('div', 'gallery-stage'), thumbs = el('div', 'thumbs'); thumbs.setAttribute('aria-label', t.ui.chooseScene);
  const dots = el('div', 'carousel-dots'); dots.setAttribute('aria-label', t.ui.chooseScene);
  const announcement = el('p', 'selection-caption'); announcement.setAttribute('role', 'status');
  const position = el('span', 'selection-position');
  const previous = button('‹', () => step(-1), 'carousel-arrow'); previous.setAttribute('aria-label', t.ui.previousImage);
  const next = button('›', () => step(1), 'carousel-arrow'); next.setAttribute('aria-label', t.ui.nextImage);
  function step(direction) {
    if (!visibleCases.length) return;
    const index = visibleCases.findIndex(c => c.id === current?.id);
    select(visibleCases[(index + direction + visibleCases.length) % visibleCases.length]);
  }
  function centerSelected() {
    // Rotate existing buttons instead of cloning experiments for the carousel.
    if (visibleCases.length >= 3) {
      const selected = visibleCases.findIndex(c => c.id === current?.id), middle = Math.floor(visibleCases.length / 2);
      const focused = thumbs.contains(document.activeElement) ? document.activeElement : null;
      const ordered = Array.from({ length: visibleCases.length }, (_, i) => visibleCases[(selected - middle + i + visibleCases.length) % visibleCases.length]);
      if (ordered.some((c, i) => thumbs.children[i]?.dataset.id !== c.id)) {
        const existing = new Map([...thumbs.children].map(b => [b.dataset.id, b]));
        for (const c of ordered) thumbs.append(existing.get(c.id));
        focused?.focus({ preventScroll: true });
      }
    }
    const active = [...thumbs.children].find(b => b.dataset.id === current?.id);
    if (active) thumbs.scrollTo({ left: thumbs.scrollLeft + active.getBoundingClientRect().left + active.clientWidth / 2 - thumbs.getBoundingClientRect().left - thumbs.clientWidth / 2, behavior: 'instant' });
  }
  function select(c) {
    if (c?.id !== current?.id) renderCase(c);
    centerSelected();
  }
  function renderCase(c, index = c?.results.findIndex(ready) ?? 0) {
    currentPlayer?.dispose(); current = c; stage.replaceChildren();
    for (const b of thumbs.children) b.setAttribute('aria-pressed', String(b.dataset.id === c?.id));
    for (const b of dots.children) b.setAttribute('aria-pressed', String(b.dataset.id === c?.id));
    if (!c) { stage.append(el('p', 'video-error', t.noResults)); announcement.textContent = ''; position.textContent = ''; return; }
    const r = c.results[Math.max(index, 0)];
    announcement.textContent = c.title;
    position.textContent = `${visibleCases.indexOf(c) + 1} / ${visibleCases.length}`;
    const chips = el('div', 'chips'); [r.method, r.version, r.trajectory].forEach(x => chips.append(el('span', 'chip', x)));
    append(stage, append(el('div', 'case-heading'), append(el('div'), el('span', 'kicker', t.generated), el('h3', '', c.title)), chips));
    if (c.results.length > 1) {
      const select = el('select'); select.setAttribute('aria-label', t.ui.resultSelector);
      c.results.forEach((r, i) => { const option = el('option', '', `${r.method} · ${r.trajectory} · ${{ready:'可播放',pending:'准备中',unavailable:'不可用'}[r.status]}`); option.value = i; select.append(option); }); select.value = Math.max(index, 0);
      select.onchange = () => renderCase(c, Number(select.value)); stage.append(select);
    }
    const result = resultFigure(r, c, { auto: true }); currentPlayer = result.player;
    stage.append(result.figure);
    requestAnimationFrame(centerSelected);
  }
  function filter(category) {
    selectedCategory = category;
    visibleCases = cases.filter(c => (collection === 'all' || c.featured !== false) && (category === '*' || c.category === category));
    thumbs.replaceChildren(); dots.replaceChildren();
    for (const c of visibleCases) {
      const b = button('', () => select(c), 'thumb'); b.dataset.id = c.id; b.setAttribute('aria-label', `查看${c.title}`);
      append(b, photo(c.inputImage, `${t.input}: ${c.title}`, true)); thumbs.append(b);
      const dot = button('', () => select(c), 'carousel-dot'); dot.dataset.id = c.id; dot.setAttribute('aria-label', `${t.ui.selectImage}: ${c.title}`); dots.append(dot);
    }
    for (const b of filters.children) b.setAttribute('aria-pressed', String(b.dataset.category === category));
    previous.disabled = next.disabled = visibleCases.length < 2;
    dots.hidden = visibleCases.length < 2;
    renderCase(visibleCases.find(c => c.id === current?.id) || visibleCases.find(c => c.results.some(ready)) || visibleCases[0]);
    requestAnimationFrame(centerSelected);
  }
  thumbs.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key) || !visibleCases.length) return;
    event.preventDefault();
    if (event.key === 'Home') select(visibleCases[0]);
    else if (event.key === 'End') select(visibleCases.at(-1));
    else step(event.key === 'ArrowLeft' ? -1 : 1);
    [...thumbs.children].find(b => b.dataset.id === current?.id)?.focus({ preventScroll: true });
  });
  // Native touch scrolling settles on the nearest original input image.
  thumbs.addEventListener('scroll', () => {
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => {
      if (!thumbs.clientWidth) return;
      const center = thumbs.getBoundingClientRect().left + thumbs.clientWidth / 2;
      const nearest = [...thumbs.children].sort((a, b) => Math.abs(a.getBoundingClientRect().left + a.clientWidth / 2 - center) - Math.abs(b.getBoundingClientRect().left + b.clientWidth / 2 - center))[0];
      const c = visibleCases.find(c => c.id === nearest?.dataset.id);
      if (c && c.id !== current?.id) renderCase(c);
    }, 140);
  }, { passive: true });
  window.addEventListener('resize', centerSelected);
  const categories = [...new Set(cases.map(c => c.category))];
  if (categories.length > 1) for (const category of ['*', ...categories]) { const b = button(category === '*' ? t.allScenes : category, () => filter(category), 'filter'); b.dataset.category = category; filters.append(b); }
  if (cases.some(c => c.featured === false)) for (const key of ['featured', 'all']) {
    const b = button(t.collections[key], () => {
      collection = key;
      for (const child of collectionControls.children) child.setAttribute('aria-pressed', String(child.dataset.collection === key));
      filter(selectedCategory);
    }, 'filter');
    b.dataset.collection = key; b.setAttribute('aria-pressed', String(key === collection)); collectionControls.append(b);
  }
  append(s, collectionControls, filters, append(el('div', 'image-selector'), previous, thumbs, next), append(el('div', 'sr-only'), announcement, position), dots, stage);
  filter('*'); return s;
}
function comparisonGroups() {
  return cases.flatMap(c => {
    const groups = new Map();
    for (const r of c.results.filter(ready)) if (r.comparisonGroup) { const group = groups.get(r.comparisonGroup) || []; group.push(r); groups.set(r.comparisonGroup, group); }
    return [...groups].filter(([, rs]) => new Set(rs.map(r => r.method)).size >= 2).map(([id, results]) => ({ id, c, results }));
  });
}
function protocolsMatch(a, b) {
  const fields = ['cameraPathHash', 'intrinsicsHash', 'sampleTimesHash', 'coordinateSystem', 'inputImageHash', 'promptHash'];
  return a.protocolAligned === true && b.protocolAligned === true && fields.every(k => a.protocol?.[k] && a.protocol[k] === b.protocol?.[k]) && a.fps === b.fps && Math.abs(a.duration - b.duration) < 0.05;
}
function comparison(groups) {
  const s = section('comparison', '03 / 同条件方法对比', 'FlashWorld × LucidDreamer'), body = el('div'); let dispose = () => {};
  function render(group) {
    dispose(); body.replaceChildren(); const { c, results } = group;
    // One result from each distinct method. Further groups can hold other trajectories.
    const a = results[0], b = results.find(r => r.method !== a.method), aligned = protocolsMatch(a, b);
    const common = append(el('div', 'compare-input'), photo(c.inputImage, `${t.input}: ${c.title}`));
    append(body, el('h3', '', c.title), common);
    const left = resultFigure(a, c, { exclusive: false }), right = resultFigure(b, c, { exclusive: false });
    const pair = [left.player, right.player], videos = pair.map(p => p.video);
    append(body, append(el('div', 'comparison-pair'), append(el('div'), left.figure), append(el('div'), right.figure)));
    // Loop at the same boundary under joint control, rather than independent native loops.
    videos.forEach(v => { v.loop = false; });
    let playing = false, waiting = false, failed = false, starting = false, generation = 0;
    const status = el('p', 'sr-only', aligned ? t.comparisonLoading : t.comparisonUnaligned); status.setAttribute('role', 'status');
    const timeline = el('input'); timeline.type = 'range'; timeline.min = 0; timeline.max = Math.min(a.duration, b.duration); timeline.step = 0.01; timeline.value = 0; timeline.setAttribute('aria-label', t.timeline);
    const loaded = () => aligned && !failed && videos.every((v, i) => v.readyState >= 3 && Math.abs(v.duration - [a,b][i].duration) < 0.1);
    function pause(resetIntent = true) { if (resetIntent) { playing = false; waiting = false; generation++; } videos.forEach(v => v.pause()); play.textContent = t.syncPlay; }
    async function start() {
      if (!loaded() || starting) { update(); return; } starting = true; const token = generation;
      playing = true; waiting = false; stopAll(pair);
      try { await Promise.all(videos.map(v => v.play())); if (token !== generation) videos.forEach(v => v.pause()); else { play.textContent = t.syncPause; status.textContent = t.comparisonAligned; } }
      catch { if (!waiting) { pause(); status.textContent = t.syncPlay; } }
      finally { starting = false; if (waiting && loaded()) queueMicrotask(start); }
    }
    const play = button(t.syncPlay, () => playing ? pause() : start());
    const restart = button(t.restart, () => {
      const resume = playing; pause(); videos.forEach(v => { v.currentTime = 0; }); timeline.value = 0;
      if (resume) { playing = true; waiting = true; }
      update(); if (resume && loaded()) start();
    });
    function update() { play.disabled = !aligned || failed || (!playing && !loaded()); restart.disabled = !loaded(); timeline.disabled = !loaded(); if (loaded() && !waiting) status.textContent = t.comparisonAligned; }
    timeline.oninput = () => { pause(); videos.forEach(v => { v.currentTime = Number(timeline.value); }); update(); };
    for (const v of videos) {
      v.addEventListener('canplay', () => { update(); if (waiting && loaded()) start(); });
      v.addEventListener('seeking', update);
      v.addEventListener('waiting', () => { if (playing) { waiting = true; videos.forEach(x => x.pause()); status.textContent = t.buffering; } update(); });
      v.addEventListener('error', () => { failed = true; pause(); update(); status.textContent = t.comparisonError; });
      v.addEventListener('pause', () => { if (v.paused && playing && !waiting && !starting) pause(); });
      v.addEventListener('ended', () => { pause(); videos.forEach(x => { x.currentTime = 0; }); timeline.value = 0; });
    }
    videos[0].addEventListener('timeupdate', () => { timeline.value = videos[0].currentTime; if (playing && !waiting && Math.abs(videos[1].currentTime - videos[0].currentTime) > 0.15) videos[1].currentTime = videos[0].currentTime; });
    append(body, append(el('div', 'sync-controls'), play, restart, timeline), status); update();
    dispose = () => { pause(); pair.forEach(p => p.dispose()); };
  }
  if (groups.length > 1) { const select = el('select'); select.setAttribute('aria-label', t.ui.comparisonSelector); groups.forEach((g, i) => { const o = el('option', '', `${g.c.title} · ${g.id}`); o.value = i; select.append(o); }); select.onchange = () => render(groups[Number(select.value)]); s.append(select); }
  s.append(body); render(groups[0]); return s;
}
function comparisonAnalysis() {
  const s = el('section', 'comparison-analysis');
  append(s, el('h3','','相机转动时，两种结果有什么不同？'),el('p','body-text','逐帧观察：起始帧两侧都保留了桌子、靠垫、黄色扶手椅与电视。到第 300–345 帧，LucidDreamer 左侧新增区域出现竖向碎片、拉伸纹理及与原图明显的拼接边界；FlashWorld 对应区域呈现较连贯的椅子、桌面与地面。'));
  const strip=el('div','evidence-grid');
  for (const [frame,label] of [['000','第000帧 · 输入锚点'],['150','第150帧 · 中间视角'],['300','第300帧 · 新露出区域'],['345','第345帧 · 轨迹终点']]) strip.append(append(el('figure'),photo(`media/comparison/frame-${frame}.png`,label)));
  s.append(strip);
  return s;
}
async function init() {
  [site, cases] = await Promise.all(['site', 'cases'].map(async name => { const response = await fetch(new URL(`./data/${name}.json`, import.meta.url)); if (!response.ok) throw Error('配置加载失败'); return response.json(); }));
  t = site.copy; $('#menu').textContent = t.ui.menu; $('#close-viewer').textContent = t.ui.close; $('.skip').textContent = t.ui.skip; document.title = site.name; $('#brand').textContent = site.name;
  const main = $('#main'); main.className = 'container'; main.replaceChildren();
  const groups = comparisonGroups();
  const nav = [['flashworld','FlashWorld'],['luciddreamer','LucidDreamer'],['comparison','方法对比'],['angles','转动角度'],['architecture','模型架构']];
  const navLinks = new Map();
  const markCurrent = id => {
    for (const [key, a] of navLinks) {
      if (key === id) a.setAttribute('aria-current', 'location');
      else a.removeAttribute('aria-current');
    }
  };
  nav.forEach(([id,label]) => {
    const a = link(label, `#${id}`);
    a.addEventListener('click', () => markCurrent(id));
    navLinks.set(id, a); $('#navigation').append(a);
  });
  let navigationFrame = 0;
  const updateCurrent = () => {
    navigationFrame = 0;
    const line = $('header').getBoundingClientRect().bottom + 130;
    let current = nav[0][0];
    for (const [id] of nav) if (document.getElementById(id)?.getBoundingClientRect().top <= line) current = id;
    markCurrent(current);
  };
  const scheduleNavigation = () => { if (!navigationFrame) navigationFrame = requestAnimationFrame(updateCurrent); };
  window.addEventListener('scroll', scheduleNavigation, { passive: true });
  window.addEventListener('resize', scheduleNavigation);
  markCurrent(nav[0][0]);
  append(main, hero(),
    gallery({id:'flashworld', ordinal:'01 / FlashWorld 结果展示',title:'FlashWorld',description:'选择原始图像，下方依次显示完整输入 text 和自动播放的新视角视频。',dataset:cases.filter(c=>c.section==='flashworld')}),
    gallery({id:'luciddreamer',ordinal:'02 / LucidDreamer 结果展示',title:'LucidDreamer',description:'选择图像，查看对应输入 text 与生成视频；各结果保留自己的相机协议。',dataset:cases.filter(c=>c.section==='luciddreamer')}));
  if (groups.length) { main.append(comparison(groups)); main.append(comparisonAnalysis()); }
  main.append(gallery({id:'angles',ordinal:'04 / 相同输入，不同转动角度',title:'同一输入，三种转动角度',description:'FlashWorld 使用相同客餐厅图像与文本，围绕固定中心分别左转30°、45°、75°。在下方选择对应的预渲染轨迹。',dataset:cases.filter(c=>c.section==='angles')}));
  main.append(architectureSection(cases));
  const resources = section('resources', '论文与资源', t.resourcesTitle); resources.classList.add('resources'); resources.append(el('p', 'body-text', t.resourcesText));
  const links = el('div', 'resource-links'); t.resources.forEach(r => links.append(link(r.label, r.url))); resources.append(links);
  main.append(resources); append($('#footer'), el('span', '', site.name), el('span', '', t.footer)); scheduleNavigation();
}
init().catch(error => { console.error(error); $('#main').replaceChildren(el('p','video-error','展示内容加载失败，请刷新页面或检查站点配置。')); });
