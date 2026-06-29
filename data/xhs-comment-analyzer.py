#!/usr/bin/env python3
"""
小红书评论区分析脚本
每天运行，搜索6个核心关键词，获取Top热门帖子，拉取评论，基于规则做智能分析。
输出 JSON 供前端展示。
"""
import json
import subprocess
import sys
import time
import re
import os
from pathlib import Path
from datetime import datetime
from collections import Counter

# === 配置 ============================================================
# 6个核心关键词 (你指定的5个 + 项目管理)
CORE_KEYWORDS = ["进销存", "财务软件", "ERP", "库存管理", "做账", "项目管理"]

# 每天分析帖子数
POSTS_PER_DAY = 5

# 每个帖子取评论数
COMMENTS_PER_POST = 30

# 历史快照保留天数
SNAPSHOT_DAYS = 7

# 数据输出目录
DATA_DIR = Path(__file__).parent
SNAPSHOT_DIR = DATA_DIR / "xhs-snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

# xhs-cli 可执行文件路径 (优先从 venv 查找)
def _find_xhs_cli():
    """自动查找 xhs-cli 可执行文件"""
    candidates = [
        Path.home() / ".agent-reach-venv" / "Scripts" / "xhs.exe",
        Path.home() / ".agent-reach-venv" / "bin" / "xhs",
        Path("/c/Users/Administrator/.agent-reach-venv/Scripts/xhs.exe"),
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    # 回退到系统 PATH
    return "xhs"

XHS_CLI = _find_xhs_cli()

# === 行业词库 =========================================================
INDUSTRIES = {
    "餐饮": ["餐饮", "饭店", "餐厅", "食堂", "美食", "外卖", "奶茶", "火锅", "饮品", "酒水", "茶饮", "小吃", "烘焙"],
    "零售/商贸": ["零售", "商贸", "批发", "门店", "超市", "便利店", "百货", "杂货", "烟酒", "水果店", "服装店", "母婴", "文具"],
    "制造/工业": ["制造", "工厂", "生产", "加工", "机械", "设备", "五金", "建材", "化工", "纺织", "印刷", "包装", "电子"],
    "电商": ["电商", "网店", "淘宝", "拼多多", "抖音小店", "快手", "直播", "跨境电商", "一件代发"],
    "建筑/工程": ["建筑", "工程", "施工", "装修", "装饰", "园林", "房地产", "开发商"],
    "汽车/汽配": ["汽车", "汽配", "修车", "4S店", "二手车", "轮胎", "配件"],
    "医药/健康": ["医药", "药品", "医疗器械", "医院", "诊所", "药店", "保健品"],
    "服务/咨询": ["服务", "咨询", "财税", "代账", "会计", "法律", "设计", "广告", "IT", "软件"],
    "贸易/进出口": ["贸易", "进出口", "外贸", "报关", "物流", "供应链", "货运"],
    "教育/培训": ["教育", "培训", "学校", "机构", "课程"],
    "农业/养殖": ["农业", "养殖", "种植", "畜牧", "渔业", "饲料"],
}

# 竞品词库
COMPETITORS = ["金蝶", "用友", "管家婆", "浪潮", "秦丝", "畅捷通", "好生意", "SAP", "Oracle", "智邦", "象过河", "百卓", "骓云", "万里牛", "聚水潭", "旺店通", "慧策", "纷享销客", "销售易", "有赞", "微盟"]

# 痛点词库
PAIN_POINTS = {
    "价格太贵": ["太贵", "贵", "价格高", "费用高", "不划算", "买不起", "成本高", "预算"],
    "功能不够": ["功能少", "不够用", "缺功能", "没有", "不支持", "不行", "达不到"],
    "操作复杂": ["复杂", "难用", "不会用", "学不会", "搞不懂", "繁琐", "麻烦", "不友好", "界面丑"],
    "数据不准": ["不准", "出错", "bug", "错误", "有问题", "对不上", "混乱"],
    "服务差": ["客服", "售后", "不理", "不回复", "态度差", "找不到人", "没人管"],
    "不稳定": ["卡", "慢", "崩溃", "闪退", "打不开", "加载", "响应慢"],
    "没人教": ["不会", "没人教", "教程少", "学不会", "不懂", "不知道怎么", "求教"],
    "行业不匹配": ["不适合", "不匹配", "行业", "不对口", "用不了"],
}

# === 工具函数 =========================================================

def run_xhs(args, timeout=60):
    """运行 xhs-cli 命令"""
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        r = subprocess.run(
            [XHS_CLI] + args,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env
        )
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""
    except FileNotFoundError:
        print(f"[错误] xhs-cli 未找到，请确保已安装", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"[错误] 运行 xhs-cli 异常: {e}", file=sys.stderr)
        return ""


def search_posts(keyword, count=10):
    """搜索关键词的热门帖子"""
    result = run_xhs(["search", keyword, "--sort", "popular", "--json"], timeout=60)
    if not result:
        return []
    try:
        data = json.loads(result)
        items = data if isinstance(data, list) else data.get("items", data.get("notes", []))
        return items[:count]
    except json.JSONDecodeError:
        return []


def get_comments(note_id, xsec_token="", count=30):
    """获取帖子评论"""
    args = ["comments", note_id]
    if xsec_token:
        args.extend(["--xsec-token", xsec_token])
    result = run_xhs(args, timeout=60)
    if not result:
        return []
    try:
        data = json.loads(result)
        items = data if isinstance(data, list) else data.get("comments", data.get("items", []))
        return items[:count]
    except json.JSONDecodeError:
        return []


def classify_industry(text):
    """基于关键词匹配识别行业"""
    scores = {}
    for industry, keywords in INDUSTRIES.items():
        score = 0
        for kw in keywords:
            if kw in text:
                score += 1
        if score > 0:
            scores[industry] = score
    if not scores:
        return "其他"
    return max(scores, key=scores.get)


def classify_intent(text):
    """识别用户意图"""
    text_lower = text.lower()
    # 咨询选型
    if any(w in text for w in ["哪个好", "怎么选", "推荐", "哪个", "适合", "选择", "选哪个", "区别", "对比", "比较好"]):
        return "咨询选型"
    # 询价
    if any(w in text for w in ["多少钱", "价格", "费用", "收费", "报价", "成本"]):
        return "询价"
    # 吐槽/负面
    if any(w in text for w in ["坑", "垃圾", "差", "不行", "后悔", "千万别", "别用", "太烂"]):
        return "吐槽竞品"
    # 求教程
    if any(w in text for w in ["怎么用", "教程", "教我", "怎么操作", "使用", "设置"]):
        return "求教程"
    # 对比竞品
    comp_count = sum(1 for c in COMPETITORS if c in text)
    if comp_count >= 2:
        return "对比竞品"
    elif comp_count == 1:
        return "提及竞品"
    # 围观/其他
    if any(w in text for w in ["收藏", "学习了", "实用", "有用", "谢谢", "感谢", "点赞"]):
        return "正面反馈"
    return "其他"


def extract_pain_points(text):
    """提取痛点"""
    found = []
    for category, keywords in PAIN_POINTS.items():
        for kw in keywords:
            if kw in text:
                found.append(category)
                break
    return list(set(found))


def extract_competitors(text):
    """提取竞品提及"""
    found = []
    for comp in COMPETITORS:
        if comp in text:
            found.append(comp)
    return found


def analyze_post(note_data, keyword):
    """分析单个帖子的评论区"""
    note_id = note_data.get("note_id") or note_data.get("id", "")
    title = note_data.get("title", "") or note_data.get("display_title", "") or note_data.get("desc", "")
    author = (note_data.get("user", {}) or {}).get("nickname", "") or note_data.get("author", "未知")
    likes = note_data.get("liked_count", 0) or note_data.get("likes", 0) or 0
    collects = note_data.get("collected_count", 0) or note_data.get("collects", 0) or 0
    comments_count = note_data.get("comments_count", 0) or note_data.get("comment_count", 0) or 0
    xsec_token = note_data.get("xsec_token", "")
    
    if not note_id or not title:
        return None
    
    # 拉取评论
    comments = get_comments(note_id, xsec_token, COMMENTS_PER_POST)
    
    # 提取评论文本
    comment_texts = []
    for c in comments:
        content = c.get("content", "") or c.get("text", "")
        if content:
            comment_texts.append(content)
    
    if not comment_texts:
        return None
    
    # === 分析 ===
    # 行业分布
    industry_counter = Counter()
    for text in comment_texts:
        ind = classify_industry(text)
        industry_counter[ind] += 1
    
    # 意图分类
    intent_counter = Counter()
    for text in comment_texts:
        intent = classify_intent(text)
        intent_counter[intent] += 1
    
    # 竞品提及
    competitor_counter = Counter()
    for text in comment_texts:
        for comp in extract_competitors(text):
            competitor_counter[comp] += 1
    
    # 痛点提取
    pain_counter = Counter()
    for text in comment_texts:
        for pp in extract_pain_points(text):
            pain_counter[pp] += 1
    
    # 代表评论 (选3条有分析价值的)
    representative = []
    for i, text in enumerate(comment_texts):
        score = 0
        # 有价值的评论：包含竞品名、行业、痛点、具体问题
        comps = extract_competitors(text)
        pains = extract_pain_points(text)
        score += len(comps) * 3
        score += len(pains) * 3
        if classify_industry(text) != "其他":
            score += 2
        if classify_intent(text) not in ["其他", "正面反馈"]:
            score += 1
        if len(text) > 20:
            score += 1
        representative.append((score, text[:200]))
    
    representative.sort(reverse=True, key=lambda x: x[0])
    top_comments = [t for _, t in representative[:3]]
    
    # 选题建议
    suggestions = generate_suggestions(title, intent_counter, pain_counter, industry_counter, competitor_counter)
    
    result = {
        "note_id": note_id,
        "title": title[:100],
        "author": author,
        "keyword": keyword,
        "likes": likes,
        "collects": collects,
        "comment_count": comments_count,
        "fetched_comments": len(comment_texts),
        "industry_distribution": dict(industry_counter.most_common(8)),
        "intent_distribution": dict(intent_counter.most_common(6)),
        "competitor_mentions": dict(competitor_counter.most_common(8)),
        "pain_points": dict(pain_counter.most_common(8)),
        "representative_comments": top_comments,
        "content_suggestions": suggestions,
        "url": f"https://www.xiaohongshu.com/explore/{note_id}",
    }
    
    return result


def generate_suggestions(title, intents, pains, industries, competitors):
    """根据评论数据反向推导内容选题建议"""
    suggestions = []
    
    # 行业相关建议
    top_industries = [ind for ind, _ in industries.most_common(3) if ind != "其他"]
    if top_industries:
        suggestions.append({
            "type": "行业针对性",
            "title": f"{'、'.join(top_industries[:2])}行业的财务软件怎么选？",
            "reason": f"评论区'{'/'.join(top_industries[:2])}'行业用户占比高，针对性内容需求明确"
        })
    
    # 竞品对比建议
    top_comps = [c for c, n in competitors.most_common(3) if n >= 1]
    if len(top_comps) >= 2:
        suggestions.append({
            "type": "竞品对比",
            "title": f"{' vs '.join(top_comps[:2])} 真实用户评价对比",
            "reason": f"评论区反复提及{'、'.join(top_comps[:2])}，用户有强烈对比需求"
        })
    
    # 痛点回应建议
    top_pains = [p for p, _ in pains.most_common(2)]
    if top_pains:
        suggestions.append({
            "type": "痛点解答",
            "title": f"关于「{top_pains[0]}」的真相——资深用户的避坑指南",
            "reason": f"评论区中'{top_pains[0]}'是最突出的用户痛点，直接回应可建立信任"
        })
    
    # 咨询选型比例高 → 横评内容
    if intents.get("咨询选型", 0) > intents.get("其他", 0):
        suggestions.append({
            "type": "选型指南",
            "title": "2026年最全选型指南：从行业到预算一步到位",
            "reason": "评论区咨询选型占比最高，系统化选型内容是刚需"
        })
    
    # 求教程 → 实操内容
    if intents.get("求教程", 0) > 1:
        suggestions.append({
            "type": "实操教程",
            "title": "新手3天上手完整教程，从0到1学会操作",
            "reason": "评论区有多条求教程的留言，实操类内容供应不足"
        })
    
    return suggestions


# === 汇总分析 =========================================================
def generate_summary(all_posts):
    """生成所有帖子的汇总分析"""
    total_comments = sum(p["fetched_comments"] for p in all_posts)
    
    # 汇总行业分布
    all_industries = Counter()
    all_intents = Counter()
    all_competitors = Counter()
    all_pains = Counter()
    
    for p in all_posts:
        for ind, cnt in p["industry_distribution"].items():
            all_industries[ind] += cnt
        for intent, cnt in p["intent_distribution"].items():
            all_intents[intent] += cnt
        for comp, cnt in p["competitor_mentions"].items():
            all_competitors[comp] += cnt
        for pain, cnt in p["pain_points"].items():
            all_pains[pain] += cnt
    
    # 最活跃的行业话题
    top_industry = all_industries.most_common(1)[0][0] if all_industries else "其他"
    
    # 评论情绪趋势 (基于intent)
    positive = all_intents.get("正面反馈", 0)
    question = all_intents.get("咨询选型", 0) + all_intents.get("询价", 0) + all_intents.get("求教程", 0)
    negative = all_intents.get("吐槽竞品", 0) + sum(all_pains.values())
    
    return {
        "total_posts": len(all_posts),
        "total_comments": total_comments,
        "top_industry": top_industry,
        "sentiment": {
            "positive": positive,
            "question": question,
            "negative": negative,
        },
        "overall_industries": dict(all_industries.most_common(10)),
        "overall_intents": dict(all_intents.most_common(6)),
        "overall_competitors": dict(all_competitors.most_common(10)),
        "overall_pain_points": dict(all_pains.most_common(10)),
    }


# === 快照管理 =========================================================
def save_snapshot(data):
    """保存今日快照，保留最近7天"""
    today = datetime.now().strftime("%Y-%m-%d")
    filepath = SNAPSHOT_DIR / f"{today}.json"
    filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    
    # 清理7天前的快照
    cutoff = datetime.now().timestamp() - SNAPSHOT_DAYS * 86400
    for f in SNAPSHOT_DIR.glob("*.json"):
        try:
            date_str = f.stem
            ts = datetime.strptime(date_str, "%Y-%m-%d").timestamp()
            if ts < cutoff:
                f.unlink()
        except (ValueError, OSError):
            pass


def load_historical_summaries():
    """加载历史快照用于趋势对比"""
    summaries = []
    for f in sorted(SNAPSHOT_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if "summary" in data:
                summaries.append({
                    "date": f.stem,
                    "summary": data["summary"]
                })
        except (json.JSONDecodeError, OSError):
            pass
    return summaries[-SNAPSHOT_DAYS:]


# === 主流程 ===========================================================
def main():
    print("=" * 50)
    print("小红书评论区分析脚本")
    print("时间:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 50)
    
    # 1. 搜索6个关键词，收集热门帖子
    all_posts_raw = []
    for kw in CORE_KEYWORDS:
        print(f"\n[搜索] {kw}...")
        posts = search_posts(kw, count=10)
        print(f"  找到 {len(posts)} 个帖子")
        for p in posts:
            p["_keyword"] = kw
        all_posts_raw.extend(posts)
        time.sleep(2)  # 避免请求过快
    
    # 2. 去重并按互动量排序，取Top 5
    seen_ids = set()
    unique_posts = []
    for p in all_posts_raw:
        nid = p.get("note_id") or p.get("id", "")
        if nid and nid not in seen_ids:
            seen_ids.add(nid)
            unique_posts.append(p)
    
    # 按互动量排序
    def interaction_score(p):
        likes = p.get("liked_count", 0) or p.get("likes", 0) or 0
        collects = p.get("collected_count", 0) or p.get("collects", 0) or 0
        comments = p.get("comments_count", 0) or p.get("comment_count", 0) or 0
        return likes + collects * 2 + comments * 3
    
    unique_posts.sort(key=interaction_score, reverse=True)
    top_posts = unique_posts[:POSTS_PER_DAY]
    
    # 3. 分析每个帖子
    print(f"\n[分析] 开始分析 Top {len(top_posts)} 帖子...")
    results = []
    for i, p in enumerate(top_posts):
        kw = p.get("_keyword", "未知")
        title = p.get("title", "") or p.get("display_title", "")
        print(f"  [{i+1}/{len(top_posts)}] {title[:50]}... ({kw})")
        result = analyze_post(p, kw)
        if result:
            results.append(result)
            print(f"    评论: {result['fetched_comments']}条 | 行业: {len(result['industry_distribution'])} | 竞品: {len(result['competitor_mentions'])}")
        time.sleep(3)  # 避免请求过快
    
    # 4. 生成汇总
    print(f"\n[汇总] 成功分析 {len(results)} 个帖子")
    summary = generate_summary(results)
    
    # 5. 加载历史数据
    historical = load_historical_summaries()
    
    # 6. 组装最终输出
    output = {
        "generated_at": datetime.now().isoformat(),
        "keywords": CORE_KEYWORDS,
        "summary": summary,
        "posts": results,
        "historical": historical,
    }
    
    # 7. 保存快照
    save_snapshot(output)
    print(f"\n[快照] 已保存到 {SNAPSHOT_DIR}")
    
    # 8. 输出 JSON
    output_path = DATA_DIR / "xhs-comment-analysis.json"
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"[输出] {output_path}")
    
    # 9. 打印简要结果
    print("\n" + "=" * 50)
    print("分析完成!")
    print(f"  帖子数: {len(results)}")
    print(f"  评论总数: {summary['total_comments']}")
    print(f"  最活跃行业: {summary['top_industry']}")
    print(f"  历史快照: {len(historical)} 天")
    print("=" * 50)


if __name__ == "__main__":
    main()
