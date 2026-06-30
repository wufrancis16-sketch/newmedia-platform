#!/usr/bin/env python3
"""
小红书评论区分析脚本 V5 — 使用 xhs CLI 命令搜索真实数据

工作原理:
  1. 调用 `xhs search 关键词 --json` 获取真实搜索结果（CLI 绕过签名问题）
  2. 取评论数最多的 Top 帖子
  3. 调用 `xhs comments 帖子ID --json` 拉取真实评论
  4. 智能分析评论（行业分布、用户意图、竞品提及、痛点提取）
  5. 输出 JSON 供前端展示，附带 AI 内容建议

依赖: xhs CLI (xhs.exe 已安装在 ~/.agent-reach-venv/Scripts/)
"""
import json
import subprocess
import sys
import time
import os
from pathlib import Path
from datetime import datetime
from collections import Counter

# Fix Windows GBK console encoding for emoji/unicode output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# === 配置 ============================================================
CORE_KEYWORDS = ["进销存", "财务软件", "ERP", "库存管理", "做账", "项目管理"]
SEARCH_PAGE_SIZE = 20         # 每关键词搜索结果数
POSTS_PER_KEYWORD = 1         # 每个关键词分析几个帖子
COMMENTS_PER_POST = 30        # 每帖子取评论数
SNAPSHOT_DAYS = 7             # 历史快照保留天数

DATA_DIR = Path(__file__).parent
# Use workspace temp for sandbox-safe writes (snapshots + output)
WORK_DIR = Path(r"C:\Users\Administrator\WorkBuddy\2026-06-29-09-20-41")
SNAPSHOT_DIR = WORK_DIR / "xhs-snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH = WORK_DIR / "xhs-comment-analysis.json"

# xhs CLI 路径
XHS_CLI = "xhs"  # 已在 PATH 中

# === 词库 =============================================================
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

COMPETITORS = [
    "金蝶", "用友", "管家婆", "浪潮", "秦丝", "畅捷通", "好生意",
    "SAP", "Oracle", "智邦", "象过河", "百卓", "骓云", "万里牛",
    "聚水潭", "旺店通", "慧策", "纷享销客", "销售易", "有赞", "微盟"
]

PAIN_POINTS = {
    "价格太贵": ["太贵", "贵", "价格高", "费用高", "不划算", "买不起", "成本高", "预算"],
    "功能不够": ["功能少", "不够用", "缺功能", "没有", "不支持", "不行", "达不到"],
    "操作复杂": ["复杂", "难用", "不会用", "学不会", "搞不懂", "繁琐", "麻烦", "不友好", "界面丑"],
    "数据不准": ["不准", "出错", "bug", "错误", "有问题", "对不上", "混乱"],
    "服务差": ["客服", "售后", "不理", "不回复", "态度差", "找不到人", "没人管"],
    "不稳定": ["卡", "慢", "崩溃", "闪退", "打不开", "加载", "响应慢"],
    "没人教": ["不会", "没人教", "教程少", "学不懂", "不懂", "不知道怎么", "求教"],
    "行业不匹配": ["不适合", "不匹配", "行业", "不对口", "用不了"],
}


# === CLI 调用 ==========================================================
def run_xhs_cli(args, timeout=30):
    """调用 xhs CLI 并返回解析后的 JSON 数据"""
    cmd = [XHS_CLI] + args + ["--json"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            encoding=None,  # bytes mode
        )
        stdout = result.stdout.decode("utf-8", errors="replace").strip()
        if not stdout:
            return None
        data = json.loads(stdout)
        if not data.get("ok"):
            return None
        return data.get("data")
    except subprocess.TimeoutExpired:
        print(f"  [超时] xhs {' '.join(args)}", file=sys.stderr)
        return None
    except (json.JSONDecodeError, Exception) as e:
        print(f"  [错误] xhs CLI: {type(e).__name__}: {str(e)[:100]}", file=sys.stderr)
        return None


def search_keyword(keyword, page_size=20):
    """搜索关键词，返回帖子列表"""
    data = run_xhs_cli(["search", keyword, "--page", "1", "--sort", "popular"], timeout=30)
    if not data:
        return []
    items = data.get("items", [])
    posts = []
    for item in items:
        nc = item.get("note_card", {})
        interact = nc.get("interact_info", {}) or {}
        posts.append({
            "note_id": item.get("id", ""),
            "xsec_token": item.get("xsec_token", ""),
            "title": nc.get("display_title", ""),
            "author": nc.get("user", {}).get("nickname", "未知"),
            "author_id": nc.get("user", {}).get("user_id", ""),
            "likes": _to_int(interact.get("liked_count", 0)),
            "collects": _to_int(interact.get("collected_count", 0)),
            "comment_count": _to_int(interact.get("comment_count", 0)),
            "type": nc.get("type", ""),
        })
    return posts


def fetch_comments(note_id, max_comments=30):
    """获取帖子评论，返回纯文本列表"""
    data = run_xhs_cli(["comments", note_id], timeout=30)
    if not data:
        return []
    raw_comments = data.get("comments", [])
    texts = []
    for c in raw_comments:
        content = c.get("content", "")
        if content and isinstance(content, str):
            texts.append(content.strip())
        # 也收集子评论
        for sub in c.get("sub_comments", []):
            sub_content = sub.get("content", "")
            if sub_content and isinstance(sub_content, str):
                texts.append(sub_content.strip())
        if len(texts) >= max_comments:
            break
    return texts[:max_comments]


def _to_int(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


# === 分析函数 =========================================================
def classify_industry(text):
    scores = {}
    for industry, keywords in INDUSTRIES.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[industry] = score
    return max(scores, key=scores.get) if scores else "其他"


def classify_intent(text):
    if any(w in text for w in ["哪个好", "怎么选", "推荐", "哪个", "适合", "选择", "选哪个", "区别", "对比", "比较好"]):
        return "咨询选型"
    if any(w in text for w in ["多少钱", "价格", "费用", "收费", "报价", "成本"]):
        return "询价"
    if any(w in text for w in ["坑", "垃圾", "差", "不行", "后悔", "千万别", "别用", "太烂"]):
        return "吐槽竞品"
    if any(w in text for w in ["怎么用", "教程", "教我", "怎么操作", "使用", "设置"]):
        return "求教程"
    comp_count = sum(1 for c in COMPETITORS if c in text)
    if comp_count >= 2:
        return "对比竞品"
    elif comp_count == 1:
        return "提及竞品"
    if any(w in text for w in ["收藏", "学习了", "实用", "有用", "谢谢", "感谢", "点赞"]):
        return "正面反馈"
    return "其他"


def extract_pain_points(text):
    found = []
    for category, keywords in PAIN_POINTS.items():
        for kw in keywords:
            if kw in text:
                found.append(category)
                break
    return list(set(found))


def extract_competitors(text):
    return [comp for comp in COMPETITORS if comp in text]


def generate_suggestions(title, intents, pains, industries, competitors):
    suggestions = []
    top_industries = [ind for ind, _ in industries.most_common(3) if ind != "其他"]
    if top_industries:
        suggestions.append({
            "type": "行业针对性",
            "title": f"{'、'.join(top_industries[:2])}行业的财务软件怎么选？",
            "reason": f"评论区'{'/'.join(top_industries[:2])}'行业用户占比高，针对性内容需求明确"
        })
    top_comps = [c for c, n in competitors.most_common(3) if n >= 1]
    if len(top_comps) >= 2:
        suggestions.append({
            "type": "竞品对比",
            "title": f"{' vs '.join(top_comps[:2])} 真实用户评价对比",
            "reason": f"评论区反复提及{'、'.join(top_comps[:2])}，用户有强烈对比需求"
        })
    top_pains = [p for p, _ in pains.most_common(2)]
    if top_pains:
        suggestions.append({
            "type": "痛点解答",
            "title": f"关于「{top_pains[0]}」的真相——资深用户的避坑指南",
            "reason": f"评论区中'{top_pains[0]}'是最突出的用户痛点，直接回应可建立信任"
        })
    if intents.get("咨询选型", 0) > intents.get("其他", 0):
        suggestions.append({
            "type": "选型指南",
            "title": "2026年最全选型指南：从行业到预算一步到位",
            "reason": "评论区咨询选型占比最高，系统化选型内容是刚需"
        })
    if intents.get("求教程", 0) > 1:
        suggestions.append({
            "type": "实操教程",
            "title": "新手3天上手完整教程，从0到1学会操作",
            "reason": "评论区有多条求教程的留言，实操类内容供应不足"
        })
    return suggestions


# === 快照管理 =========================================================
def save_snapshot(data):
    today = datetime.now().strftime("%Y-%m-%d")
    filepath = SNAPSHOT_DIR / f"{today}.json"
    filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    cutoff = datetime.now().timestamp() - SNAPSHOT_DAYS * 86400
    for f in SNAPSHOT_DIR.glob("*.json"):
        try:
            ts = datetime.strptime(f.stem, "%Y-%m-%d").timestamp()
            if ts < cutoff:
                f.unlink()
        except (ValueError, OSError):
            pass


def load_historical_summaries():
    summaries = []
    # Try workspace snapshots first, then data/ snapshots
    search_dirs = [SNAPSHOT_DIR]
    old_dir = DATA_DIR / "xhs-snapshots"
    if old_dir.exists():
        search_dirs.append(old_dir)
    for search_dir in search_dirs:
        for f in sorted(search_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if "summary" in data:
                    summaries.append({"date": f.stem, "summary": data["summary"]})
            except (json.JSONDecodeError, OSError):
                pass
    return summaries[-SNAPSHOT_DAYS:]


def build_empty_result(keyword, title="", note_id="", author="未知",
                       likes=0, collects=0, comment_count=0):
    note_id = note_id or f"no_match_{keyword}"
    return {
        "note_id": note_id,
        "title": title[:100] or f"「{keyword}」相关帖（待刷新）",
        "author": author,
        "keyword": keyword,
        "likes": likes,
        "collects": collects,
        "comment_count": comment_count,
        "fetched_comments": 0,
        "industry_distribution": {},
        "intent_distribution": {},
        "competitor_mentions": {},
        "pain_points": {},
        "representative_comments": [],
        "content_suggestions": [],
        "url": (f"https://www.xiaohongshu.com/explore/{note_id}"
                if note_id and not note_id.startswith("no_match") else ""),
    }


# === 核心抓取 V5: xhs CLI ==============================================
def fetch_all():
    results = []

    print("=" * 55)
    print("小红书评论区分析 V5 - xhs CLI 真实数据抓取")
    print("时间:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 55)

    for kw in CORE_KEYWORDS:
        print(f"\n[关键词] {kw}")

        # 1. 搜索
        posts = search_keyword(kw, SEARCH_PAGE_SIZE)
        print(f"  搜索结果: {len(posts)} 条帖子")

        if not posts:
            print(f"  ⚠️ 无搜索结果")
            results.append(build_empty_result(kw, "暂无匹配帖子"))
            time.sleep(2)
            continue

        # 2. 按评论数排序，取最有讨论度的帖子
        posts.sort(key=lambda x: x["comment_count"], reverse=True)
        top_posts = posts[:POSTS_PER_KEYWORD]

        for post in top_posts:
            note_id = post["note_id"]
            title = post["title"]
            author = post["author"]
            likes = post["likes"]
            collects = post["collects"]
            comment_count = post["comment_count"]

            print(f"  帖子: {title[:55]}")
            print(f"    作者: {author} | 👍{likes} ⭐{collects} 💬{comment_count}")

            if not note_id:
                results.append(build_empty_result(kw, title))
                continue

            # 3. 获取评论
            time.sleep(2)
            comment_texts = []
            if comment_count > 0:
                comment_texts = fetch_comments(note_id, COMMENTS_PER_POST)
            print(f"    评论: 获取 {len(comment_texts)} 条")

            if not comment_texts:
                results.append(build_empty_result(
                    kw, title, note_id, author, likes, collects, comment_count
                ))
                continue

            # 4. 智能分析评论
            industry_counter = Counter()
            intent_counter = Counter()
            competitor_counter = Counter()
            pain_counter = Counter()

            for text in comment_texts:
                industry_counter[classify_industry(text)] += 1
                intent_counter[classify_intent(text)] += 1
                for comp in extract_competitors(text):
                    competitor_counter[comp] += 1
                for pp in extract_pain_points(text):
                    pain_counter[pp] += 1

            # 5. 代表评论（按信息量评分）
            scored = []
            for text in comment_texts:
                score = 0
                score += len(extract_competitors(text)) * 3
                score += len(extract_pain_points(text)) * 3
                if classify_industry(text) != "其他":
                    score += 2
                if classify_intent(text) not in ["其他", "正面反馈"]:
                    score += 1
                if len(text) > 20:
                    score += 1
                scored.append((score, text[:200]))
            scored.sort(reverse=True, key=lambda x: x[0])
            top_comments = [t for _, t in scored[:3]]

            # 6. 选题建议
            suggestions = generate_suggestions(
                title, intent_counter, pain_counter,
                industry_counter, competitor_counter
            )

            results.append({
                "note_id": note_id,
                "title": title[:100],
                "author": author,
                "keyword": kw,
                "likes": likes,
                "collects": collects,
                "comment_count": comment_count,
                "fetched_comments": len(comment_texts),
                "industry_distribution": dict(industry_counter.most_common(8)),
                "intent_distribution": dict(intent_counter.most_common(6)),
                "competitor_mentions": dict(competitor_counter.most_common(8)),
                "pain_points": dict(pain_counter.most_common(8)),
                "representative_comments": top_comments,
                "content_suggestions": suggestions,
                "url": f"https://www.xiaohongshu.com/explore/{note_id}",
            })

            stat = (f"行业{len(industry_counter)} 竞品{len(competitor_counter)} "
                    f"痛点{len(pain_counter)}")
            print(f"    分析: {stat} ✅")

        time.sleep(2)

    with_data = len([r for r in results if r.get("fetched_comments", 0) > 0])
    print(f"\n[完成] {with_data}/{len(results)} 个帖子有真实评论数据")
    return results


# === 汇总 =============================================================
def generate_summary(all_posts):
    total_comments = sum(p["fetched_comments"] for p in all_posts)
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

    top_industry = all_industries.most_common(1)
    top_industry_name = top_industry[0][0] if top_industry else "其他"
    positive = all_intents.get("正面反馈", 0)
    question = (all_intents.get("咨询选型", 0) +
                all_intents.get("询价", 0) +
                all_intents.get("求教程", 0))
    negative = all_intents.get("吐槽竞品", 0) + sum(all_pains.values())

    return {
        "total_posts": len(all_posts),
        "total_comments": total_comments,
        "top_industry": top_industry_name,
        "sentiment": {"positive": positive, "question": question, "negative": negative},
        "overall_industries": dict(all_industries.most_common(10)),
        "overall_intents": dict(all_intents.most_common(6)),
        "overall_competitors": dict(all_competitors.most_common(10)),
        "overall_pain_points": dict(all_pains.most_common(10)),
    }


# === 主流程 ===========================================================
def main():
    output_path = OUTPUT_PATH

    try:
        posts = fetch_all()
    except Exception as e:
        print(f"[致命错误] 抓取失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        if output_path.exists():
            print("[回退] 使用上一次的 JSON 数据", file=sys.stderr)
            existing_data = json.loads(output_path.read_text(encoding="utf-8"))
            existing_data["generated_at"] = datetime.now().isoformat()
            existing_data["_warning"] = f"本次抓取失败({str(e)[:100]})，显示缓存数据"
            output_path.write_text(
                json.dumps(existing_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        sys.exit(1)
        return

    if not posts:
        print("[警告] 未获取到任何帖子，保持现有数据不变", file=sys.stderr)
        return

    posts_with_data = [p for p in posts if p.get("fetched_comments", 0) > 0]
    summary = generate_summary(posts_with_data if posts_with_data else posts)

    output = {
        "generated_at": datetime.now().isoformat(),
        "keywords": CORE_KEYWORDS,
        "summary": summary,
        "posts": posts,
        "historical": load_historical_summaries(),
    }

    save_snapshot(output)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 55)
    print("分析完成!")
    for p in posts:
        has = "✅" if p["fetched_comments"] > 0 else "⬜"
        print(f"  {has} [{p['keyword']}] 👍{p['likes']} ⭐{p['collects']} "
              f"💬{p['comment_count']} | {p['title'][:45]}")
    print(f"  帖子总数: {len(posts)}")
    print(f"  评论总数: {summary['total_comments']}")
    print(f"  输出文件: {output_path}")
    print("=" * 55)


if __name__ == "__main__":
    main()
