# 新媒体数据平台 - 项目记忆

## 部署架构
- **GitHub Pages**: https://wufrancis16-sketch.github.io/newmedia （每次 push 自动更新）
- **CloudStudio**: https://c6a433e5c3494aaaa8df87797848fd89.app.codebuddy.work/
- **GitHub 仓库**: https://github.com/wufrancis16-sketch/newmedia

## 自动化流程
- 每天 9:00 自动运行：数据更新 → 同步到 newmedia-deploy → git push
- CloudStudio 部署：每次数据更新后自动部署到 CloudStudio
- Git push 偶发 SSL/TLS 握手失败，重试一次即可

## ⚠️ 重要规则：自动部署 CloudStudio
- 在本项目的交互式会话中，只要修改了 `public/` 目录下的任何文件，**必须自动部署到 CloudStudio**，不需要用户额外说"部署到 CloudStudio"
- 部署工具: `workbuddy_cloudstudio_deploy`，目标目录: `C:\Users\Administrator\WorkBuddy\2026-05-28-14-46-37\newmedia-platform\public`
- 部署完成后告知用户 CloudStudio 链接即可

## 数据显示规则
- **抓取数量**: 每个平台抓取数量随机（30-99条），基于日期生成
- **界面显示**: 显示完整真实数据量，不再显示随机子集
- **修改位置**: 
  - `update-data.js`：修改 TARGET_DOUYIN/TARGET_WECHAT/TARGET_XHS 为随机值
  - `app.js`：修改 `getPlatformData` 函数，返回完整数据

## 词云数据流（2026-06-26，17:25 用户参考图定稿：去业务化 + 圆形布局）
- **定位**：完全去业务化，展示"小红书/抖音/公众号爆款标题中出现的高频热词"
- **入口**: `renderKeywordCloud(container)` 读取 `KEYWORD_CLOUD_DATA` 全局变量
- **数据源**：从 201 条抓取到的真实标题中按词频匹配
- **词库** `VIRAL_WORDS`（~160 个，**不包含任何业务词**，全部为人群/身份/通用热词）：
  - 人群/身份（核心）：小白/新手/学生党/大学生/打工人/宝妈/女生/老板/老师/朋友/姐妹/兄弟/同事/搭子/...
  - 学习工作：学习/工作/办公/职场/教程/指南/技巧/干货
  - 吸引/结果：免费/推荐/分享/种草/必看/避坑/真香/亲测
  - 数字/限定：10个/最全/最强/必入
  - 反差/悬念：居然/原来/对比/测评/区别
  - 行为/动作：怎么做/怎么选/教你/手把手/保姆级
  - 生活场景：旅游/美食/穿搭/健身
  - 情绪：救命/天呐/破防/治愈
- **生成**: `update-data.js` 的 `generateTrendingKeywordCloud(appJs)`
  - 从 REAL_DATA 中提取 201 条标题
  - 对每个词做正则匹配计数（用 escape 防元字符）
  - 过滤出现次数为 0 的词
  - Top30 截取 + TRENDING_FALLBACK 兜底
  - 归一化权重到 10-100
- **展示**: `app.js` 的 `renderKeywordCloud` 用 **Archimedean 椭圆螺旋 + AABB 矩形碰撞检测**（2026-06-29 修复）
  - 最大词放画布正中，后续词从第 1 圈开始按椭圆周长均匀采样角度逐圈外扩
  - 用 `getBoundingClientRect()` 测每个词的真实像素尺寸，按旋转角算外接矩形做碰撞
  - 中心大词（按权重降序），外圈小词
  - 单一蓝色调（hsl 220, 35-60% 亮度）
  - 字号 19-48px 随权重
  - 旋转 -35° ~ 35° 错落
  - 浅蓝渐变背景 + 圆角 16px
- **CSS**: `.cloud-canvas`（aspect-ratio 16/9, max-height 560px, position: relative），`.cloud-word`（position: absolute）
  - ⚠️ 关键：算法坐标系必须与 CSS aspect-ratio 一致，否则坐标会溢出画布
- **注入正则**: `/const KEYWORD_CLOUD_DATA = \[[\s\S]*?\n\];|const KEYWORD_CLOUD_DATA = \{[\s\S]*?\n\};/` 兼容空对象
- **不要让词云数据回到硬编码或业务词**，每日 9:00 自动化必须包含词云生成

## 目录结构
- 数据源 + 脚本: `newmedia-platform/`
- 部署目录（GitHub 推送）: `newmedia-deploy/`
- `public/` 目录是最终产出的静态网站文件
