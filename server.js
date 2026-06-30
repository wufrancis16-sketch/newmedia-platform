const express = require('express');
const cors = require('cors');
const path = require('path');
const scraper = require('./data/scraper');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// ============================================================
// API 路由
// ============================================================

// 获取所有平台热门内容
app.get('/api/hot', async (req, res) => {
  try {
    const data = await scraper.fetchAllPlatforms();
    res.json({ success: true, data, updateTime: new Date().toISOString() });
  } catch (error) {
    res.status(500).json({ success: false, message: '数据获取失败', error: error.message });
  }
});

// 获取单个平台热门内容
app.get('/api/hot/:platform', async (req, res) => {
  try {
    const { platform } = req.params;
    const data = await scraper.fetchPlatformData(platform);
    if (!data) {
      return res.status(404).json({ success: false, message: `暂无 ${platform} 的实时数据` });
    }
    res.json({ success: true, data, updateTime: new Date().toISOString() });
  } catch (error) {
    res.status(500).json({ success: false, message: '数据获取失败', error: error.message });
  }
});

// 平台统计概览
app.get('/api/stats', async (req, res) => {
  try {
    const allData = await scraper.fetchAllPlatforms();
    const stats = Object.entries(allData)
      .filter(([, p]) => p && p.items)
      .map(([key, platform]) => ({
        platform: key,
        platformName: platform.platformName,
        contentCount: platform.items.length,
        totalLikes: platform.items.reduce((s, i) => s + (i.likes || 0), 0),
        totalComments: platform.items.reduce((s, i) => s + (i.comments || 0), 0),
        totalShares: platform.items.reduce((s, i) => s + (i.shares || 0), 0),
        source: platform.source || 'unknown'
      }));
    res.json({ success: true, data: stats, updateTime: new Date().toISOString() });
  } catch (error) {
    res.status(500).json({ success: false, message: '统计获取失败', error: error.message });
  }
});

// 小红书评论区分析数据
app.get('/api/comment-analysis', (req, res) => {
  try {
    const fs = require('fs');
    const jsonPath = path.join(__dirname, 'data', 'xhs-comment-analysis.json');
    if (fs.existsSync(jsonPath)) {
      const raw = fs.readFileSync(jsonPath, 'utf-8');
      const data = JSON.parse(raw);
      res.json({ success: true, data });
    } else {
      res.json({ success: false, message: '评论分析数据文件不存在' });
    }
  } catch (error) {
    res.status(500).json({ success: false, message: '读取失败', error: error.message });
  }
});

// 健康检查
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', platform: '新媒体数据平台', uptime: process.uptime(), timestamp: new Date().toISOString() });
});

// SPA fallback
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 新媒体数据平台已启动`);
  console.log(`📍 本地访问: http://localhost:${PORT}`);
  console.log(`📊 API: GET /api/hot | /api/hot/:platform | /api/stats | /api/health`);
});
