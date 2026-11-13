#!/usr/bin/env node
'use strict';
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');

const args={};
for(let i=2;i<process.argv.length;i+=2){
 if(!['--dir','--modules','--browser'].includes(process.argv[i])||!process.argv[i+1])throw new Error('用法：--dir 输出目录 [--modules node_modules路径] [--browser 浏览器路径]');
 args[process.argv[i].slice(2)]=process.argv[i+1];
}
if(!args.dir)throw new Error('请提供 --dir 输出目录');
let chromium;
try{
 ({chromium}=args.modules?require(path.join(path.resolve(args.modules),'playwright')):require('playwright'));
}catch(e){
 console.error('未找到 Playwright。请复用已有依赖并提供 --modules，或按照 references/workflow.md 准备本地工具目录。');
 process.exit(1);
}
const base=path.resolve(args.dir);
const read=name=>JSON.parse(fs.readFileSync(path.join(base,name),'utf8'));
const normalize=t=>t.replace(/\s+/g,'');
const sha=data=>crypto.createHash('sha256').update(data).digest('hex');
function fingerprint(names){
 const hash=crypto.createHash('sha256');
 for(const name of [...names].sort())hash.update(name,'utf8').update('\0').update(fs.readFileSync(path.join(base,name))).update('\0');
 return hash.digest('hex');
}
function browserPath(){
 const candidates=[args.browser,process.env.WECHAT_BROWSER_PATH,chromium.executablePath(),
 '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
 '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
 '/usr/bin/chromium','/usr/bin/chromium-browser','/usr/bin/google-chrome'];
 for(const root of [process.env.PROGRAMFILES,process.env['PROGRAMFILES(X86)'],process.env.LOCALAPPDATA].filter(Boolean)){
  candidates.push(path.join(root,'Google','Chrome','Application','chrome.exe'));
  candidates.push(path.join(root,'Microsoft','Edge','Application','msedge.exe'));
 }
 if(args.browser&&!fs.existsSync(args.browser))throw new Error('--browser 指定的文件不存在。');
 const found=candidates.find(p=>p&&fs.existsSync(p));
 if(!found)throw new Error('未找到浏览器，请指定 --browser 或安装 Playwright Chromium。');
 return found;
}

(async()=>{
 const record=read('构建记录.json');
 assert.equal(fingerprint(record.fingerprint_files),record.fingerprint,'构建后文件已有变化，请重建。');
 for(const item of record.images)assert.equal(sha(fs.readFileSync(path.join(base,'配图',item.filename))),item.sha256,'图片与原始素材字节不一致');
 const warnings=[],errors=[],mobile=[];
 const browser=await chromium.launch({headless:true,executablePath:browserPath()});
 const report={passed:false,skill_version:record.skill_version,fingerprint:record.fingerprint,mobile,warnings,errors,wechat_backend_verified:false};
 try{
  const context=await browser.newContext({viewport:{width:390,height:900},deviceScaleFactor:2});
  try{await context.grantPermissions(['clipboard-read','clipboard-write']);}catch(e){warnings.push('浏览器不支持预先授予剪贴板读取权限。');}
  const page=await context.newPage();
  page.setDefaultTimeout(15000);
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.join(base,'公众号排版预览.html')).href);
  await page.evaluate(()=>Promise.all([...document.images].map(i=>i.decode())));
  for(const width of [360,390,430]){
   await page.setViewportSize({width,height:900});
   const state=await page.locator('#article').evaluate(el=>{
    const r=el.getBoundingClientRect(),h=el.querySelector('h1');
    const overflow=[...el.querySelectorAll('*')].filter(x=>{const b=x.getBoundingClientRect();return b.width>0&&(b.left<r.left-1||b.right>r.right+1);}).map(x=>x.textContent.slice(0,60));
    const paragraphs=[...el.querySelectorAll('[data-paragraph]')].map(p=>({text:p.innerText,lines:Math.round(p.getBoundingClientRect().height/parseFloat(getComputedStyle(p).lineHeight))}));
    return{width:r.width,overflow,title:h.innerText,titleLines:Math.round(h.getBoundingClientRect().height/parseFloat(getComputedStyle(h).lineHeight)),
     longParagraphs:paragraphs.filter(x=>x.lines>6),
     images:[...el.querySelectorAll('img')].map(i=>({number:i.dataset.imageNumber,loaded:i.complete&&i.naturalWidth>0,ratioError:Math.abs(i.getBoundingClientRect().width/i.getBoundingClientRect().height-i.naturalWidth/i.naturalHeight)}))};
   });
   assert.equal(state.overflow.length,0,'手机正文存在横向溢出');
   assert.equal(normalize(state.title),normalize(record.title),'首屏标题不一致');
   if(record.expected_title_lines)assert.equal(state.titleLines,record.expected_title_lines,'标题出现意外换行，请调整分行');
   assert.equal(state.images.length,record.images.length,'预览图片数不一致');
   assert(state.images.every(i=>i.loaded&&i.ratioError<0.02),'图片加载失败或比例不正确');
   if(state.longParagraphs.length)warnings.push(width+'px 下有 '+state.longParagraphs.length+' 段超过 6 行，需审阅。');
   mobile.push({viewport:width,...state});
   if(width===390){
    const checks=path.join(base,'检查素材');fs.mkdirSync(checks,{recursive:true});
    await page.locator('#article').screenshot({path:path.join(base,'手机预览.png')});
    await page.evaluate(()=>window.scrollTo(0,0));
    const box=await page.locator('#article').boundingBox();
    await page.screenshot({path:path.join(base,'首屏预览.png'),fullPage:true,clip:{x:box.x,y:box.y,width:box.width,height:Math.min(1000,box.height)}});
    for(const item of record.images){
     await page.locator('img[data-image-number="'+item.number+'"]').locator('..').screenshot({path:path.join(checks,String(item.number).padStart(2,'0')+'_配图.png')});
    }
   }
  }
  const body=normalize(await page.locator('#article').innerText());
  const missing=record.source_texts.filter(x=>!body.includes(normalize(x)));
  assert.deepEqual(missing,[],'正文或图注有缺失');
  report.source_blocks_checked=record.source_texts.length;
  await page.getByRole('button',{name:'查看图片占位',exact:true}).click();
  assert.equal(await page.locator('[data-image-placeholder]').count(),record.images.length);
  assert.equal(await page.locator('#article img:visible').count(),0);
  for(const item of record.images){
   const placeholder=await page.locator('[data-image-placeholder="'+item.number+'"]').innerText();
   assert(placeholder.includes(item.alt)&&placeholder.includes(item.filename),'占位缺少图片内容或文件名');
  }
  report.placeholder_switch=true;
  await page.evaluate(()=>{window.__copyPayload=null;window.addEventListener('copy',e=>{window.__copyPayload={html:e.clipboardData.getData('text/html'),text:e.clipboardData.getData('text/plain')};});});
  await page.getByRole('button',{name:'复制正文排版',exact:true}).click();
  const captured=await page.evaluate(()=>window.__copyPayload);
  assert(captured&&captured.html.includes('background-color'),'未生成富文本剪贴板内容');
  assert(!captured.html.includes('<script')&&!captured.html.includes('<img')&&!captured.html.includes('复制正文排版'));
  assert.equal((captured.text.match(/【配图/g)||[]).length,record.images.length);
  for(const item of record.images)assert(captured.text.includes(item.filename),'复制的图片编号缺失');
  report.copy={event_payload:true,system_clipboard:false,title:false,summary:false};
  let actual=null;
  try{
   actual=await page.evaluate(async()=>{const items=await navigator.clipboard.read();let html='',text='';for(const item of items){if(item.types.includes('text/html'))html=await(await item.getType('text/html')).text();if(item.types.includes('text/plain'))text=await(await item.getType('text/plain')).text();}return{html,text};});
  }catch(e){warnings.push('系统剪贴板读取受限；已检查复制事件内容，未验证系统剪贴板。');}
  if(actual){
   assert(actual.html.includes('background-color'));
   assert.equal(actual.text,captured.text);
   report.copy.system_clipboard=true;
  }
  for(const [name,expected,key] of [['复制标题',record.title,'title'],['复制摘要',record.summary,'summary']]){
   await page.getByRole('button',{name,exact:true}).click();
   assert.equal(await page.evaluate(()=>window.__copyPayload.text),expected);
   if(report.copy.system_clipboard)assert.equal(await page.evaluate(()=>navigator.clipboard.readText()),expected);
   report.copy[key]=true;
  }
  await page.setViewportSize({width:1100,height:1000});
  await page.getByRole('button',{name:'切换宽屏预览',exact:true}).click();
  assert.equal(Math.round((await page.locator('#article').boundingBox()).width),640);
  await page.getByRole('button',{name:'切换手机预览',exact:true}).click();
  assert.equal(Math.round((await page.locator('#article').boundingBox()).width),420);
  await page.getByRole('button',{name:'查看配图效果',exact:true}).click();
  assert.equal(await page.locator('[data-image-placeholder]').count(),0);
  assert.equal(await page.locator('#article img:visible').count(),record.images.length);
  await page.goto(pathToFileURL(path.join(base,'公众号正文.html')).href);
  await page.evaluate(()=>Promise.all([...document.images].map(i=>i.decode())));
  assert.equal(await page.locator('img').count(),record.images.length);
  assert(await page.locator('img').evaluateAll(images=>images.every(i=>i.complete&&i.naturalWidth>0)));
  assert.equal(normalize(await page.locator('#article').innerText()),body);
  await page.goto(pathToFileURL(path.join(base,'初稿_图片占位.html')).href);
  assert.equal(await page.locator('img').count(),0);
  assert.equal(await page.locator('[data-image-placeholder]').count(),record.images.length);
  const draftText=normalize(await page.locator('#article').innerText());
  assert(record.source_texts.every(x=>draftText.includes(normalize(x))),'占位初稿丢失正文或图注');
  for(const width of [360,390,430]){
   await page.setViewportSize({width,height:900});
   const overflow=await page.locator('#article').evaluate(el=>{const r=el.getBoundingClientRect();return [...el.querySelectorAll('*')].filter(x=>{const b=x.getBoundingClientRect();return b.width>0&&(b.left<r.left-1||b.right>r.right+1);}).length;});
   assert.equal(overflow,0,'占位初稿存在横向溢出');
   if(width===390){
    await page.locator('#article').screenshot({path:path.join(base,'初稿_图片占位.png')});
    if(record.images.length)await page.locator('[data-image-placeholder]').first().locator('..').screenshot({path:path.join(base,'检查素材/图片占位示例.png')});
   }
  }
  report.draft_placeholders=record.images.length;
  assert.deepEqual(errors,[]);
  report.standalone_images=record.images.length;
  report.image_bytes_preserved=true;
  report.passed=true;
 }catch(e){
  report.failure=e.message;
  throw e;
 }finally{
  fs.writeFileSync(path.join(base,'检查报告.json'),JSON.stringify(report,null,2));
  await browser.close();
 }
 console.log(JSON.stringify({passed:report.passed,images:record.images.length,draft_placeholders:report.draft_placeholders,placeholder_switch:report.placeholder_switch,viewports:mobile.map(x=>x.viewport),copy:report.copy,warnings}));
})().catch(e=>{console.error('检查未通过：'+e.message);process.exit(1);});
