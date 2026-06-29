// 抖音数据抓取书签 - 复制下面的代码到书签网址

javascript:void(function(){
  let items = [];
  document.querySelectorAll('li[data-e2e="scroll-list"] > div, [class*="video-card"]').forEach(card => {
    let titleEl = card.querySelector('[class*="title"], [class*="author"], a[title]');
    let linkEl = card.querySelector('a[href*="/video/"]');
    let statsEls = card.querySelectorAll('[class*="count"], [class*="num"], span');
    
    let title = titleEl ? titleEl.textContent.trim() : '';
    let url = linkEl ? linkEl.href : '';
    let stats = [];
    
    statsEls.forEach(el => {
      let text = el.textContent.trim();
      if (text.match(/^\d+(\.\d+)?[万亿]?$/)) {
        stats.push(text);
      }
    });
    
    if (title && url && url.includes('/video/')) {
      items.push({
        title: title,
        url: url,
        stats: stats.join(' | ')
      });
    }
  });
  
  if (items.length === 0) {
    alert('未找到视频数据，请确保页面已加载完成');
    return;
  }
  
  let result = JSON.stringify(items.slice(0, 20), null, 2);
  
  // 创建弹窗
  let div = document.createElement('div');
  div.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#fff;border:2px solid #7C3AED;border-radius:12px;padding:20px;z-index:99999;max-width:500px;max-height:60vh;overflow:auto;font-size:12px;box-shadow:0 8px 24px rgba(0,0,0,0.3);font-family:monospace';
  div.innerHTML = '<div style="margin-bottom:10px;font-size:14px;font-weight:bold;color:#7C3AED">抓取到 ' + items.length + ' 条数据</div><pre style="margin:0;white-space:pre-wrap;word-break:break-all">' + result + '</pre><button onclick="navigator.clipboard.writeText(document.querySelector(\'[data-result]\').textContent).then(()=>this.textContent=\'已复制!\')" data-result="' + result.replace(/"/g, '&quot;') + '" style="margin-top:12px;padding:8px 16px;background:#7C3AED;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px">复制数据</button><button onclick="this.parentElement.remove()" style="margin-top:12px;margin-left:8px;padding:8px 16px;background:#666;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px">关闭</button>';
  document.body.appendChild(div);
})();
