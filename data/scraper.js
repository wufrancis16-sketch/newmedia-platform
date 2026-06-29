/**
 * 新媒体数据采集模块 - 真实数据版
 *
 * 数据源：
 * - 抖音热搜: uapis.cn 公开 API
 * - 公众号热文: tophub.today 抓取
 * - 小红书: 暂无免费公开 API（待接入）
 */

const https = require('https');
const http = require('http');

// ============================================================
// 通用 HTTP 请求
// ============================================================
function httpGet(url, timeout = 10000) {
  return new Promise((resolve, reject) => {
    const mod = url.startsWith('https') ? https : http;
    const req = mod.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      },
      timeout
    }, (res) => {
      // 处理重定向
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return httpGet(res.headers.location, timeout).then(resolve).catch(reject);
      }
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(data));
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('Request timeout')); });
  });
}

// ============================================================
// 格式化数字
// ============================================================
function formatHotValue(val) {
  if (!val) return '0';
  const num = parseInt(val);
  if (isNaN(num)) return val;
  if (num >= 100000000) return (num / 100000000).toFixed(1) + '亿';
  if (num >= 10000) return (num / 10000).toFixed(1) + '万';
  return num.toLocaleString();
}

// ============================================================
// 抖音热搜 - uapis.cn
// ============================================================
async function fetchDouyinHot() {
  try {
    const raw = await httpGet('https://uapis.cn/api/v1/misc/hotboard?type=douyin');
    const json = JSON.parse(raw);

    if (!json.list || !Array.isArray(json.list)) {
      throw new Error('Invalid response format');
    }

    return {
      platform: 'douyin',
      platformName: '抖音',
      updateTime: json.update_time || new Date().toISOString(),
      source: 'uapis.cn',
      items: json.list.slice(0, 50).map((item, i) => ({
        rank: i + 1,
        title: item.title,
        author: '抖音热搜',
        likes: parseInt(item.hot_value) || 0,
        comments: item.extra?.view_count || 0,
        shares: item.extra?.video_count || 0,
        tag: '热搜',
        summary: `热度 ${formatHotValue(item.hot_value)} · ${item.extra?.view_count ? formatHotValue(item.extra.view_count) + '次播放' : ''}`,
        url: item.url,
        cover: item.extra?.cover || ''
      }))
    };
  } catch (err) {
    console.error('抖音数据获取失败:', err.message);
    return null;
  }
}

// ============================================================
// 公众号热文 - tophub.today
// ============================================================
async function fetchWechatHot() {
  try {
    const raw = await httpGet('https://tophub.today/n/WnBe01o371');
    const items = [];
    const regex = /<a[^>]+href="(https:\/\/mp\.weixin\.qq\.com[^"]*)"[^>]*>([^<]+)<\/a>/gi;
    let match;
    let rank = 0;

    while ((match = regex.exec(raw)) !== null && rank < 30) {
      const title = match[2].trim();
      if (title && title.length > 2) {
        rank++;
        items.push({
          rank,
          title,
          author: '微信公众号',
          likes: 0, comments: 0, shares: 0,
          tag: '热文',
          summary: '微信24小时热文',
          url: match[1],
          cover: ''
        });
      }
    }

    return {
      platform: 'wechat',
      platformName: '公众号',
      updateTime: new Date().toISOString(),
      source: 'tophub.today',
      items
    };
  } catch (err) {
    console.error('公众号数据获取失败:', err.message);
    return null;
  }
}

// ============================================================
// 小红书 - 暂无免费公开 API
// ============================================================
async function fetchXiaohongshuHot() {
  // 小红书没有公开的免费热榜 API
  // 返回 null，前端会显示"暂无实时数据"
  return null;
}

// ============================================================
// 统一入口
// ============================================================
async function fetchPlatformData(platform) {
  switch (platform) {
    case 'douyin': return await fetchDouyinHot();
    case 'wechat': return await fetchWechatHot();
    case 'xiaohongshu': return await fetchXiaohongshuHot();
    default: return null;
  }
}

async function fetchAllPlatforms() {
  const [douyin, wechat, xiaohongshu] = await Promise.all([
    fetchDouyinHot(),
    fetchWechatHot(),
    fetchXiaohongshuHot()
  ]);

  return { douyin, wechat, xiaohongshu };
}

module.exports = {
  fetchPlatformData,
  fetchAllPlatforms,
  fetchDouyinHot,
  fetchWechatHot,
  fetchXiaohongshuHot
};
