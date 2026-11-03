const make=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;};
const append=(e,...xs)=>{e.append(...xs);return e;};
function demonstration(imagePath){
 const root=make('div','teaching-demo');root.append(make('h3','','直观理解'));
 const row=make('div','noise-row');const image=new Image();image.src=imagePath;
 image.onload=()=>{for(const amount of [0,.3,.65,1]){const f=make('figure'),canvas=make('canvas');canvas.width=224;canvas.height=153;const ctx=canvas.getContext('2d');ctx.drawImage(image,0,0,224,153);const data=ctx.getImageData(0,0,224,153);let seed=913;const random=()=>{seed=(1664525*seed+1013904223)>>>0;return(seed+1)/4294967297;};for(let i=0;i<data.data.length;i+=4){for(let c=0;c<3;c++){const noise=Math.sqrt(-2*Math.log(random()))*Math.cos(2*Math.PI*random());data.data[i+c]=Math.max(0,Math.min(255,(1-amount)*data.data[i+c]+amount*(128+noise*45)));}}ctx.putImageData(data,0,0);canvas.setAttribute('aria-label',`噪声强度 ${amount}`);f.append(canvas);row.append(f);}};
 root.append(row);
 const mask=make('div','mask-demo');const photo=make('img');photo.src=imagePath;photo.alt='原始图像与人为标注的未知区域示意';const overlay=make('div','mask-overlay');overlay.textContent='未覆盖区域';mask.append(photo,overlay);root.append(make('h3','','投影 → 未覆盖区域 → 图像补全'),mask);
 return root;
}
export function architectureSection(cases){
 const root=make('section','section architecture');root.id='architecture';root.append(make('div','kicker','05 / 模型架构与原理'),make('h2','','从整体流程到各个组件'),make('p','body-text','FlashWorld 与 LucidDreamer 的整体流程与组件。'));
 for(const model of [{name:'FlashWorld',slug:'flashworld',height:1840},{name:'LucidDreamer',slug:'luciddreamer',height:2380}]){
  const article=make('article',`architecture-model ${model.slug}-architecture`);
  article.append(make('h3','',`${model.name} · 模型架构`));
  const file=`media/architecture/${model.slug}-v0.10.0.svg`;
  const diagramLink=make('a','architecture-file-link');diagramLink.href=file;diagramLink.target='_blank';diagramLink.rel='noopener noreferrer';diagramLink.setAttribute('aria-label',`打开 ${model.name} 架构图原始 SVG`);
  const figure=make('img','architecture-file-image');figure.src=file;figure.alt=`${model.name} 模型架构图`;figure.width=1500;figure.height=model.height;figure.loading='lazy';figure.decoding='async';
  diagramLink.append(figure);article.append(diagramLink);root.append(article);
 }
 const training=make('div','training-note');training.append(make('h3','','上游模型训练与本次推理的区别'),make('p','','FlashWorld 的上游训练路线：双模式预训练 → 多视图模式教师向三维模式学生做跨模式蒸馏 → 获得推理权重。这里没有重新训练教师或学生。LucidDreamer 本案例中的 2990 步是逐场景高斯优化，不是 SD 扩散模型微调。'));root.append(training);
 const paired=cases.find(c=>c.id==='paired-room40');if(paired)root.append(demonstration(paired.inputImage));
 const why=make('div','mechanism-analysis');why.append(make('h3','','为什么本案例中 FlashWorld 没有出现相同的明显伪影？'),make('p','body-text','本案例观察：FlashWorld 没有表现出 LucidDreamer 新增左侧区域那样严重的碎片拼接。机制上的合理解释是：联合多视图信息与三维渲染反馈，可以减少逐视角补全、反复深度估计与融合带来的误差累积。LucidDreamer 的图像补全质量、深度与对齐相互依赖；最终高斯优化也可能保留错误的生成监督。'),);
 root.append(why);
 const references=make('div','resource-links');for(const [name,url] of [['FlashWorld · 论文方法第3节','https://arxiv.org/html/2510.13678v1#S3'],['FlashWorld · 固定版本实现','https://github.com/imlixinyang/FlashWorld/blob/424db4487de308a39e5137afbe85e7568a96193f/app.py'],['LucidDreamer · 论文方法第3节','https://arxiv.org/html/2311.13384v2#S3'],['LucidDreamer · 官方实现','https://github.com/luciddreamer-cvlab/LucidDreamer']]){const a=make('a','',name);a.href=url;a.target='_blank';a.rel='noopener noreferrer';references.append(a);}root.append(references);return root;
}
