#!/usr/bin/env python3
"""《精致大学生的第0课》构建工具：同一份 Markdown 源生成导航、数据合并、检查与 A4 PDF。

用法（在仓库根目录）：
  python3 tools/book.py nav     # 刷新每篇文末上一课／回目录／下一课
  python3 tools/book.py merge   # 合并 data/fragments/* 为 data/prices.tsv、sources.tsv、book/术语表.md 素材
  python3 tools/book.py check   # 检查内链、数据表可解析、ID 唯一、source_id 存在
  python3 tools/book.py pdf     # 生成 dist/精致大学生的第0课.pdf
  python3 tools/book.py all
依赖：python3、markdown、weasyprint、Noto Sans/Serif CJK SC 字体（见 docs/导出说明.md）。
"""
import csv, glob, html, os, re, sys, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
VERSION = "v0.4.0"
DATE = "2026-10-21"
NAV_RE = re.compile(r"(<!-- NAV -->|<!-- NAV:BEGIN -->.*?<!-- NAV:END -->)", re.S)


def topics():
    return list(csv.DictReader(open("data/topics.tsv", encoding="utf-8"), delimiter="\t"))


def rel(frm, to):
    return os.path.relpath(to, os.path.dirname(frm)).replace(os.sep, "/")


# ---------------- nav ----------------
def cmd_nav():
    ts = topics()
    for i, t in enumerate(ts):
        p = t["path"]
        if not os.path.exists(p):
            print("missing", p); continue
        parts = []
        if i > 0:
            pv = ts[i - 1]
            parts.append(f"上一课：[{pv['title']}]({rel(p, pv['path'])})")
        parts.append(f"[回目录]({rel(p, 'README.md')})")
        if i < len(ts) - 1:
            nx = ts[i + 1]
            parts.append(f"下一课：[{nx['title']}]({rel(p, nx['path'])})")
        nav = "<!-- NAV:BEGIN -->\n---\n\n" + " · ".join(parts) + "\n<!-- NAV:END -->"
        s = open(p, encoding="utf-8").read()
        if NAV_RE.search(s):
            s = NAV_RE.sub(lambda m: nav, s, count=1)
        else:
            s = s.rstrip() + "\n\n" + nav + "\n"
        open(p, "w", encoding="utf-8").write(s)
    print("nav ok")


# ---------------- merge ----------------
def read_tsv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE))


def write_tsv(path, cols, rows):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join((r.get(c) or "").replace("\t", " ").replace("\n", " ").strip() for c in cols) + "\n")


PRICE_COLS = "price_id topic_id city institution item amount currency unit includes excludes price_type effective_date accessed_date source_id notes".split()
SRC_COLS = "source_id title url publisher source_type published_date accessed_date verification_status supports topic_ids".split()
TERM_COLS = "term aliases definition topic_ids".split()


def cmd_merge():
    for kind, cols, out in [("prices", PRICE_COLS, "data/prices.tsv"), ("sources", SRC_COLS, "data/sources.tsv"), ("terms", TERM_COLS, "data/terms.tsv")]:
        rows = []
        for fp in sorted(glob.glob(f"data/fragments/*-{kind}.tsv")):
            for r in read_tsv(fp):
                r = {k.strip() if k else k: v for k, v in r.items()}
                if any((r.get(c) or "").strip() for c in cols):
                    rows.append(r)
        write_tsv(out, cols, rows)
        print(out, len(rows))


# ---------------- check ----------------
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)|<img[^>]*src=\"([^\"]+)\"")


def cmd_check():
    errs = []
    mds = [p for p in glob.glob("**/*.md", recursive=True) if not p.startswith(("资料包", "work/", "node_modules"))]
    for p in mds:
        s = open(p, encoding="utf-8").read()
        s = re.sub(r"```.*?```", "", s, flags=re.S)
        s = re.sub(r"`[^`\n]*`", "", s)
        for m in LINK_RE.finditer(s):
            from urllib.parse import unquote
            u = unquote(m.group(1) or m.group(2))
            if re.match(r"^(https?:|mailto:|#)", u):
                continue
            target = os.path.normpath(os.path.join(os.path.dirname(p), u.split("#")[0]))
            if not os.path.exists(target):
                errs.append(f"broken link {p} -> {u}")
    for fp in ["data/brand-identifiers.tsv", "data/topics.tsv", "data/prices.tsv", "data/sources.tsv", "data/terms.tsv", "data/outlet-stores.tsv", "data/dining-comparisons.tsv", "data/platform-observations.tsv"]:
        if not os.path.exists(fp):
            errs.append(f"missing {fp}"); continue
        rows = read_tsv(fp)
        hdr = open(fp, encoding="utf-8").readline().rstrip("\n").split("\t")
        for i, line in enumerate(open(fp, encoding="utf-8").read().splitlines()[1:], 2):
            if line.count("\t") != len(hdr) - 1:
                errs.append(f"{fp}:{i} has {line.count(chr(9))+1} cols, expected {len(hdr)}")
    srcs = read_tsv("data/sources.tsv") if os.path.exists("data/sources.tsv") else []
    ids = [r["source_id"] for r in srcs]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup: errs.append(f"duplicate source_id {sorted(dup)}")
    pr = read_tsv("data/prices.tsv") if os.path.exists("data/prices.tsv") else []
    pids = [r["price_id"] for r in pr]
    dupp = {i for i in pids if pids.count(i) > 1}
    if dupp: errs.append(f"duplicate price_id {sorted(dupp)}")
    sid = set(ids)
    for r in pr:
        for s in re.split(r"[;,，；\s]+", r.get("source_id") or ""):
            if s and s not in sid:
                errs.append(f"price {r['price_id']} cites unknown {s}")
    for t in topics():
        if not os.path.exists(t["path"]):
            errs.append(f"missing article {t['path']}"); continue
        body = open(t["path"], encoding="utf-8").read().split("<!-- NAV")[0]
        h1 = body.lstrip().splitlines()[0]
        if re.match(r"^#\s+[A-Z]\d{2}\b", h1):
            errs.append(f"H1 still has ID prefix: {t['path']}")
        if h1.strip() != "# " + t["title"]:
            errs.append(f"H1 differs from topics title: {t['path']}")
        if "适用范围" in body:
            errs.append(f"meta line 适用范围 left: {t['path']}")
        for bad in ["商标归", "CC BY", "assets/logos", "data/", "SRC-", "v0.", "无法确认", "核验", "待核", "样本", "口径", "本轮", "抓取", "检索", "适用范围", "仅作识别"]:
            if bad in body:
                errs.append(f"internal wording '{bad}' in {t['path']}")
        if "## 来源" in body:
            errs.append(f"use '## 参考' not '## 来源': {t['path']}")
        main = body.split("\n## 参考")[0]
        ntab = len(re.findall(r"^\|[-: |]+\|\s*$", main, flags=re.M))
        if ntab > 1:
            errs.append(f"{ntab} tables in body (max 1): {t['path']}")
    print("\n".join(errs) if errs else "check ok")
    print(f"{len(errs)} issue(s)")
    return errs


# ---------------- pdf ----------------
def slug_for(path):
    return "f-" + re.sub(r"[^0-9A-Za-z]+", "-", Path(path).stem.split("-")[0]).strip("-")


def md_to_html(text, src_path, anchor_map):
    import markdown
    text = re.sub(r"<!-- NAV:BEGIN -->.*?<!-- NAV:END -->", "", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    # GitHub <details>: keep content visible in PDF
    text = re.sub(r"<details>\s*<summary>(.*?)</summary>", r'<div class="details"><p class="summary">\1</p>\n', text, flags=re.S)
    text = text.replace("</details>", "</div>")
    md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists", "attr_list", "md_in_html", "toc"],
                           extension_configs={"toc": {"slugify": lambda v, s: ""}})
    h = md.convert(text)
    prefix = anchor_map.get(os.path.normpath(src_path), "x")

    def fix(m):
        from urllib.parse import unquote
        u = unquote(html.unescape(m.group(1)))
        if re.match(r"^(https?:|mailto:)", u):
            return m.group(0)
        if u.startswith("#"):
            return f'href="#{prefix}"'
        target = os.path.normpath(os.path.join(os.path.dirname(src_path), u.split("#")[0]))
        if target in anchor_map:
            return f'href="#{anchor_map[target]}"'
        return 'href="#"'
    h = re.sub(r'href="([^"]+)"', fix, h)
    def fiximg(m):
        from urllib.parse import unquote
        u = unquote(m.group(1))
        if re.match(r"^(https?:|file:|data:)", u):
            return m.group(0)
        ap = os.path.abspath(os.path.join(os.path.dirname(src_path), u))
        return f'src="file://{ap}"'
    h = re.sub(r'src="([^"]+)"', fiximg, h)
    h = re.sub(r"<h([1-6]) id=\"[^\"]*\">", r"<h\1>", h)
    def nw(m):
        inner = re.sub(r"<[^>]+>", "", m.group(2))
        ok = 0 < len(inner) <= 6 or (len(inner) <= 11 and re.fullmatch(r'[A-Za-z0-9\-\.]+', inner))
        return f'<{m.group(1)} class="nw">{m.group(2)}</{m.group(1)}>' if ok else m.group(0)
    h = re.sub(r"<(td|th)>(.*?)</\1>", nw, h, flags=re.S)
    return h


CSS = """
@font-face { font-family: 'NSans'; src: url('file://FONTDIR/NotoSansCJKsc-Regular.otf'); font-weight: 400; }
@font-face { font-family: 'NSans'; src: url('file://FONTDIR/NotoSansCJKsc-Bold.otf'); font-weight: 700; }
@font-face { font-family: 'NSerif'; src: url('file://FONTDIR/NotoSerifCJKsc-Regular.otf'); font-weight: 400; }
@font-face { font-family: 'NSerif'; src: url('file://FONTDIR/NotoSerifCJKsc-Bold.otf'); font-weight: 700; }
@page { size: A4; margin: 20mm 19mm 20mm 19mm;
  @top-left { content: string(chap); font: 8.5pt 'NSans'; color: #666; }
  @top-right { content: "精致大学生的第0课"; font: 8.5pt 'NSans'; color: #999; }
  @bottom-center { content: counter(page); font: 9pt 'NSans'; color: #555; } }
@page cover { margin: 0; @top-left{content:none} @top-right{content:none} @bottom-center{content:none} }
@page front { @top-left{content:none} @bottom-center { content: counter(page, lower-roman); font: 9pt 'NSans'; color:#555;} }
html { font-family: 'NSerif', serif; font-size: 10.8pt; line-height: 1.65; color: #1d1d1f; }
body { margin: 0; }
h1, h2, h3, h4, th, .meta, .toc, blockquote, table, .cover, .navline { font-family: 'NSans', sans-serif; }
h1 { font-size: 19pt; line-height: 1.3; margin: 0 0 6pt; color: #111; bookmark-level: 2; string-set: chap content(); }
h2 { font-size: 13.5pt; margin: 18pt 0 6pt; padding-bottom: 2pt; border-bottom: 0.6pt solid #ccc; bookmark-level: 3; }
h3 { font-size: 11.5pt; margin: 12pt 0 4pt; bookmark-level: none; }
h4 { font-size: 10.8pt; bookmark-level: none; }
h1, h2, h3, h4 { page-break-after: avoid; break-after: avoid; }
p { margin: 0 0 7pt; orphans: 2; widows: 2; text-align: justify; }
a { color: #0b57d0; text-decoration: none; overflow-wrap: anywhere; }
ul, ol { margin: 0 0 7pt; padding-left: 18pt; } li { margin: 1.5pt 0; }
blockquote { margin: 7pt 0; padding: 5pt 10pt; border-left: 3pt solid #8a8a8a; background: #f4f4f4; font-size: 10pt; break-inside: avoid; }
blockquote p { margin: 2pt 0; text-align: left; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 8.8pt; line-height: 1.45; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
th, td { border: 0.5pt solid #bbb; padding: 3pt 4.5pt; vertical-align: top; text-align: left; overflow-wrap: anywhere; }
th { background: #ececec; font-weight: 700; }
.nw { white-space: nowrap; }
img { max-width: 100%; vertical-align: middle; }
td img { max-height: 18pt; max-width: 60pt; }
code { font-family: 'NSans'; font-size: 9pt; background: #f2f2f2; padding: 0 2pt; }
pre { background: #f2f2f2; padding: 6pt; font-size: 8.5pt; white-space: pre-wrap; overflow-wrap: anywhere; }
pre code { background: none; padding: 0; }
strong { font-weight: 700; }
hr { border: 0; border-top: 0.5pt solid #ccc; margin: 10pt 0; }
.details { border: 0.5pt dashed #aaa; padding: 4pt 8pt; margin: 6pt 0; }
.details .summary { font-family: 'NSans'; font-weight: 700; }
.chapter { break-before: page; }
.part { break-before: page; padding-top: 70mm; }
.part h1.parttitle { font-size: 26pt; bookmark-level: 1; string-set: chap content(); border: 0; }
.part p { font-family: 'NSans'; color: #555; }
.cover { page: cover; height: 297mm; padding: 70mm 22mm 0; box-sizing: border-box; background: #f5f1ea; }
.cover .t { font-size: 34pt; font-weight: 700; color: #111; line-height: 1.25; bookmark-level: 1; bookmark-label: "封面"; }
.cover .s { font-size: 14pt; color: #444; margin-top: 10pt; }
.cover .m { position: absolute; bottom: 30mm; font-size: 10pt; color: #555; line-height: 1.8; }
.front { page: front; }
.toc h1 { string-set: chap "目录"; bookmark-level: 1; }
.toc ul { list-style: none; padding: 0; } .toc li { margin: 2.5pt 0; font-size: 10.2pt; }
.toc li.part { font-weight: 700; margin-top: 9pt; padding: 0; break-before: auto; }
.toc a { color: #111; } .toc a::after { content: leader('.') target-counter(attr(href), page); color: #555; }
"""


def cmd_pdf():
    from weasyprint import HTML
    fontdir = os.environ.get("BOOK_FONT_DIR", "/workspace/work/fonts")
    ts = topics()
    # sections: (part title, [paths])
    parts = [("写在前面", ["book/前言.md"])]
    order = {}
    for t in ts:
        order.setdefault(t["part"], []).append(t["path"])
    for pt, ps in order.items():
        parts.append((pt, ps))
    anchor_map = {}
    for _, ps in parts:
        for p in ps:
            anchor_map[os.path.normpath(p)] = slug_for(p) if re.match(r"^[A-Z]\d\d", Path(p).stem) else "f-" + str(abs(hash(p)) % 10**8)
    anchor_map[os.path.normpath("README.md")] = "toc"
    body = []
    body.append(f'<section class="cover"><div class="t">精致大学生的第0课</div><div class="s">给刚来大城市的你：把自己收拾体面，再大大方方走进去</div>'
                f'<div class="m">dan · pkusi.com</div></section>')
    toc = ['<section class="toc front chapter" id="toc"><h1>目录</h1><ul>']
    for pi, (pt, ps) in enumerate(parts):
        toc.append(f'<li class="part"><a href="#part-{pi}">{html.escape(pt)}</a></li>')
        for p in ps:
            if not os.path.exists(p): continue
            first = next((l for l in open(p, encoding="utf-8") if l.startswith("# ")), "# " + Path(p).stem)[2:].strip()
            toc.append(f'<li><a href="#{anchor_map[os.path.normpath(p)]}">{html.escape(first)}</a></li>')
    toc.append("</ul></section>")
    body.append("".join(toc))
    for pi, (pt, ps) in enumerate(parts):
        body.append(f'<section class="part" id="part-{pi}"><h1 class="parttitle">{html.escape(pt)}</h1></section>')
        for p in ps:
            if not os.path.exists(p):
                print("skip missing", p); continue
            h = md_to_html(open(p, encoding="utf-8").read(), p, anchor_map)
            body.append(f'<section class="chapter" id="{anchor_map[os.path.normpath(p)]}">{h}</section>')
    doc = f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>精致大学生的第0课</title><style>{CSS.replace("FONTDIR", fontdir).replace("VERSION", VERSION)}</style></head><body>{"".join(body)}</body></html>'
    os.makedirs("dist", exist_ok=True)
    open("dist/book.html", "w", encoding="utf-8").write(doc)
    HTML(string=doc, base_url=str(ROOT)).write_pdf("dist/精致大学生的第0课.pdf")
    print("pdf ok", os.path.getsize("dist/精致大学生的第0课.pdf"))



# ---------------- tables (appendix md generated from data) ----------------
def _cell(x):
    return (x or "").replace("|", "／").strip()


def _link(title, url):
    return f"[{_cell(title) or url}]({url})" if url and url.startswith("http") else _cell(title)


PT_ZH = {"government_guide": "政府指导价", "institution_posted": "机构公示价", "promo": "活动价", "list": "官网/挂牌价", "menu": "菜单价", "platform_listing": "平台展示价", "individual_quote": "个案报价", "wholesale_reference": "采购/批发参考"}
ST_ZH = {"government_policy": "政策文件", "institution_price": "机构价目", "professional_guideline": "专业指南", "hospital_education": "医院科普", "merchant_rule": "商户规则", "platform_rule": "平台规则", "video": "视频", "personal_experience": "个人经验", "news": "新闻", "reference_repo": "参考仓库", "platform_listing": "平台展示页"}


def cmd_tables():
    ts = {t["topic_id"]: t for t in topics()}
    old2new = {}
    for t in ts.values():
        for o in (t.get("merged_from") or "").split(";"):
            if o.strip(): old2new[o.strip()] = t["topic_id"]
    def tlink(tid, frm):
        tid = old2new.get(tid.strip(), tid.strip())
        t = ts.get(tid)
        return f"[{t['title']}]({rel(frm, t['path'])})" if t else _cell(tid)
    # 费用样本表
    pr = read_tsv("data/prices.tsv"); src = {r["source_id"]: r for r in read_tsv("data/sources.tsv")}
    out = ["# 费用样本表", "", f"整理日期：{DATE} · 数据源：`data/prices.tsv`", "",
           "每一行是某机构或渠道在某日公示、展示或报价的**单个样本**，不是市场平均价。完整字段（包含、另收、生效日期、备注）见 `data/prices.tsv`；本页只保留手机上读得下的列。", ""]
    by = {}
    for r in pr:
        k = r["topic_id"].split(",")[0].strip()
        by.setdefault(old2new.get(k, k), []).append(r)
    for tid in ts:
        if tid not in by: continue
        out += [f"## {ts[tid]['title']}", "", "| 城市·机构 | 项目 | 金额／单位 | 性质·日期 |", "|---|---|---|---|"]
        for r in by[tid]:
            s = src.get((r.get("source_id") or "").split(";")[0].split(",")[0].strip())
            inst = _link(r["institution"], s["url"]) if s else _cell(r["institution"])
            date = r.get("effective_date") or r.get("accessed_date")
            out.append(f"| {_cell(r['city'])}·{inst} | {_cell(r['item'])} | {_cell(r['amount'])} {_cell(r['currency'])}／{_cell(r['unit'])} | {PT_ZH.get(r['price_type'].strip(), _cell(r['price_type']))}·{_cell(date)} |")
        out.append("")
    open("docs/资料/费用样本表.md", "w", encoding="utf-8").write("\n".join(out) + "\n")
    # 来源记录
    status = {"read_supported": "已读且支持", "located_only": "仅定位", "restricted": "受限", "conflict": "冲突待核"}
    out = ["# 来源记录", "", f"整理日期：{DATE} · 数据源：`data/sources.tsv`", "",
           "核验状态只说明本轮是否打开并读到支持内容，不等于来源的医学证据等级。“受限”表示登录、限流或超时，不代表内容不存在，也不代表已核实。", ""]
    groups = {}
    for r in read_tsv("data/sources.tsv"):
        groups.setdefault(r["source_id"].split("-")[1] if "-" in r["source_id"] else "?", []).append(r)
    gname = {"D": "牙齿", "E": "视力", "S": "皮肤", "H": "理发", "F": "健身", "B": "品牌与奥莱", "V": "餐厅", "C": "吃饭省钱", "P": "场所"}
    for g in "DESHFBVCP":
        if g not in groups: continue
        out += [f"## {gname[g]}", "", "| ID | 来源 | 类型·日期 | 状态 | 支持什么 |", "|---|---|---|---|---|"]
        for r in groups[g]:
            out.append(f"| {r['source_id']} | {_link(r['title'], r['url'])}（{_cell(r['publisher'])}） | {ST_ZH.get(r['source_type'].strip(), _cell(r['source_type']))}·{_cell(r['published_date'] or '未标')} | {status.get(r['verification_status'], _cell(r['verification_status']))} | {_cell(r['supports'])} |")
        out.append("")
    open("docs/资料/来源记录.md", "w", encoding="utf-8").write("\n".join(out) + "\n")
    # 奥莱品牌目录
    if os.path.exists("data/outlet-stores.tsv"):
        rows = read_tsv("data/outlet-stores.tsv")
        out = ["# 奥莱品牌目录", "", f"整理日期：{DATE} · 数据源：`data/outlet-stores.tsv`", "",
               "这里的每一行是一条**门店记录**，不是一个独立品牌：同一品牌的成人线、童装线、不同写法会各占一行，集合店、餐饮和服务另列。正文只列零售门店（品牌店与童装线）；餐饮、服务和占位记录留在数据表。“编辑分组”是本书为了帮助理解做的品类分组，**不是官方评级**。目录只证明官方页面在采集日列出了这家店，不证明当前在营、所有商品在售或同集团品牌也入驻。认牌方法见 [认识奢侈品牌](../../book/4-逛店不怯场/奢侈品牌.md) 与 [运动和户外品牌](../../book/4-逛店不怯场/运动户外品牌.md)。", ""]
        og = {}
        for r in rows: og.setdefault(r["outlet"], []).append(r)
        from collections import Counter
        out += ["| 奥莱 | 城市 | 门店记录 | 其中零售门店 | 独立品牌（按规范名归并） |", "|---|---|---|---|---|"]
        for o, rs in og.items():
            ret = [r for r in rs if r.get("entity_type") in ("brand_store", "kids_line")]
            nb = len({(r.get("brand_canonical") or r["brand"]).strip().lower() for r in rs if r.get("entity_type") not in ("placeholder", "food_beverage", "service")})
            out.append(f"| {_cell(o)} | {_cell(rs[0].get('outlet_city'))} | {len(rs)} | {len(ret)} | {nb} |")
        out.append("")
        for o, rs in og.items():
            url = rs[0].get("official_directory_url") or rs[0].get("official_listing_url", "")
            st = Counter((r.get("verification_status") or "").strip() for r in rs)
            ret = [r for r in rs if r.get("entity_type") in ("brand_store", "kids_line")]
            out += [f"## {o}", "", f"官方目录：{_link('官方品牌目录', url)} · 采集：{_cell(rs[0].get('accessed_date'))} · 门店记录 {len(rs)} 条，下表列零售门店 {len(ret)} 条 · 状态：" + "；".join(f"{_cell(k)} {v}" for k, v in st.items()), ""]
            if not ret:
                out += ["官方暂无可用的门店名单，只保留项目占位。", ""]
                continue
            out += ["| 门店名 | 规范品牌 | 类型 | 品类 | 位置 |", "|---|---|---|---|---|"]
            for r in ret:
                et = {"brand_store": "品牌店", "kids_line": "童装线"}.get(r.get("entity_type"), "")
                out.append(f"| {_cell(r.get('store_display_name') or r['brand'])} | {_cell(r.get('brand_canonical'))} | {et} | {_cell(r['category'])} | {_cell(r.get('unit_or_zone'))} |")
            out.append("")
        open("docs/资料/奥莱品牌目录.md", "w", encoding="utf-8").write("\n".join(out) + "\n")
    if os.path.exists("data/dining-comparisons.tsv"):
        rows = read_tsv("data/dining-comparisons.tsv")
        out = ["# 同店同餐比价记录", "", f"整理日期：{DATE} · 数据源：`data/dining-comparisons.tsv`", "",
               "每条记录只对那家门店、那一天、那份套餐成立。标为 unverified 的行没有可公开复核的价格证据，**不能**用来证明哪个渠道最便宜。比价方法见 [吃饭省钱](../../book/2-吃得明白/吃饭省钱.md)。", "",
               "| 编号 | 城市·门店·日期 | 套餐·人数 | 渠道·标价 | 到手总价 | 状态 |", "|---|---|---|---|---|---|"]
        for r in rows:
            out.append(f"| {_cell(r['comparison_id'])} | {_cell(r['city'])}·{_link(r['store'], r.get('evidence_url'))}·{_cell(r['date_observed'])} | {_cell(r['dishes'])}·{_cell(r['party_size'])}人 | {_cell(r['channel'])}·{_cell(r['listed_price'])} | {_cell(r['total_out_of_pocket'])} | {_cell(r['verification_status'])} |")
        open("docs/资料/同店同餐比价记录.md", "w", encoding="utf-8").write("\n".join(out) + "\n")
    # 术语表
    terms = read_tsv("data/terms.tsv")
    gname = {"D": "牙齿", "E": "视力", "S": "皮肤", "H": "理发", "F": "健身", "B": "品牌与奥莱", "V": "餐厅", "C": "吃饭省钱", "P": "场所"}
    out = ["# 术语表", "", f"整理日期：{DATE} · 数据源：`data/terms.tsv`", "",
           "按章节分组。每条只给本书用到的含义；医学术语的准确诊断以医生面诊为准。", ""]
    grp = {}
    for r in terms:
        first = re.split(r"[;,，；\s]+", r["topic_ids"].strip())[0] if r["topic_ids"].strip() else "?"
        grp.setdefault(first[:1], []).append(r)
    for g in "DESHFBVCP":
        if g not in grp: continue
        out += [f"## {gname[g]}", "", "| 术语 | 也叫 | 意思 | 见 |", "|---|---|---|---|"]
        for r in sorted(grp[g], key=lambda x: x["term"]):
            ids = [i for i in re.split(r"[;,，；\s]+", r["topic_ids"]) if i]
            links = "、".join(tlink(i, "docs/资料/术语表.md") for i in ids)
            out.append(f"| **{_cell(r['term'])}** | {_cell(r['aliases']).replace(';', '、')} | {_cell(r['definition'])} | {links} |")
        out.append("")
    open("docs/资料/术语表.md", "w", encoding="utf-8").write("\n".join(out) + "\n")
    print("tables ok")



# ---------------- site (个人网站文章汇总导出) ----------------
def cmd_site():
    """导出到 dist/site/：posts/*.md 带 front matter，images/ 为用到的图，index.md 为文章汇总。"""
    import shutil
    out = "dist/site"
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out + "/posts"); os.makedirs(out + "/images")
    ts = topics()
    slug = {os.path.normpath(t["path"]): f"jingzhi-{t['topic_id']}" for t in ts}
    slug[os.path.normpath("book/前言.md")] = "jingzhi-00"
    items = [("写在前面", "book/前言.md", "00")] + [(t["part"], t["path"], t["topic_id"]) for t in ts]
    index = ["---", "title: 精致大学生的第0课", f"date: {DATE}", "---", "", "# 精致大学生的第0课", "",
             "给刚来大城市的你：把自己收拾体面，再大大方方走进去。", ""]
    cur = None
    for part, p, tid in items:
        s = open(p, encoding="utf-8").read()
        s = NAV_RE.sub("", s).rstrip() + "\n"
        title = s.splitlines()[0][2:].strip()
        body = "\n".join(s.splitlines()[1:]).strip()
        first = next((l for l in body.splitlines() if l.strip() and not l.startswith(("#", "!", ">", "|", "-"))), "")
        summary = re.split(r"(?<=[。！？])", first)[0][:80]
        def img(m):
            src = os.path.normpath(os.path.join(os.path.dirname(p), m.group(2)))
            if os.path.exists(src):
                shutil.copy(src, f"{out}/images/{os.path.basename(src)}")
                return f"![{m.group(1)}](../images/{os.path.basename(src)})"
            return m.group(0)
        body = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", img, body)
        def lk(m):
            from urllib.parse import unquote
            u = unquote(m.group(2))
            if re.match(r"^(https?:|mailto:|#)", u): return m.group(0)
            tgt = os.path.normpath(os.path.join(os.path.dirname(p), u.split("#")[0]))
            return f"[{m.group(1)}]({slug[tgt]}.md)" if tgt in slug else m.group(1)
        body = re.sub(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)", lk, body)
        fm = ["---", f"title: \"{title}\"", f"date: {DATE}", f"series: 精致大学生的第0课", f"category: {part}",
              f"order: {int(tid)}", f"summary: \"{summary}\"", "---", ""]
        open(f"{out}/posts/{slug[os.path.normpath(p)]}.md", "w", encoding="utf-8").write("\n".join(fm) + body + "\n")
        if part != cur:
            index += ["", f"## {part}", ""]; cur = part
        index.append(f"- [{title}](posts/{slug[os.path.normpath(p)]}.md)")
    open(f"{out}/index.md", "w", encoding="utf-8").write("\n".join(index) + "\n")
    print("site ok", len(items))


# ---------------- web (静态网页版，部署到 pkusi.com/yuppie/) ----------------
WEB_CSS = """
/* 叠加在 pkusi.com/site.css 之上，沿用个人主页的配色、字体与虚线分隔 */
body{font-family:var(--sans),"PingFang SC","Hiragino Sans GB","Noto Sans CJK SC","Microsoft YaHei",sans-serif}
.nav-link{white-space:nowrap}
.sec-head h2{font-family:"Songti SC","Noto Serif CJK SC","Source Han Serif SC",var(--serif);font-weight:600;font-size:24px;white-space:nowrap}
.y-hero{padding:56px var(--pad) 34px}
.y-hero .name{font-size:44px;white-space:normal;line-height:1.15}
.y-hero .name .zh{font-family:"Songti SC","Noto Serif CJK SC","Source Han Serif SC",var(--serif);font-weight:600;letter-spacing:.02em}
.y-hero .role{margin-top:12px;font-size:13px}
.y-hero .lede{margin-top:18px;color:var(--fg-2);line-height:1.8;max-width:34em}
.y-links{display:flex;flex-wrap:wrap;gap:8px;margin-top:20px}
.y-pill{display:inline-flex;align-items:center;height:30px;padding:0 13px;border-radius:99px;border:1px solid var(--edge);background:var(--card);font:500 12.5px/1 var(--sans);color:var(--fg-2);transition:border-color .2s,background-color .2s,color .2s}
.y-pill:hover{color:var(--fg);border-color:var(--line-2);background:var(--hover)}
.y-toc>a{display:grid;grid-template-columns:44px 1fr;gap:12px;padding:13px 0;transition:color .2s}
.y-toc>a+a{border-top:1px dashed var(--line)}
.y-toc .k{font:12px/1.9 var(--mono);color:var(--soft)}
.y-toc b{display:block;font-weight:500;color:var(--fg);line-height:1.5}
.y-toc span.s{display:block;margin-top:3px;font-size:13.5px;line-height:1.6;color:var(--muted)}
.y-toc>a:hover b{text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--line-2)}
.y-art-head{padding:44px var(--pad) 22px}
.y-art-head .k{font:12px/1 var(--mono);color:var(--soft)}
.y-art-head h1{margin-top:14px;font-family:"Songti SC","Noto Serif CJK SC","Source Han Serif SC",var(--serif);font-weight:600;font-size:32px;line-height:1.3;letter-spacing:.01em}
.prose{font-size:16px}
.prose p,.prose li{color:var(--fg-2);line-height:1.9}
.prose p+p{margin-top:16px}
.prose h2{margin:40px 0 14px;font-size:20px;font-weight:600;line-height:1.4;color:var(--fg)}
.prose h3{margin:28px 0 10px;font-size:17px;font-weight:600}
.prose strong,.prose b{font-weight:600;color:var(--fg)}
.prose a{color:var(--fg);text-decoration:underline;text-decoration-color:var(--line-2);text-underline-offset:3px}
.prose a:hover{text-decoration-color:var(--fg)}
.prose ul,.prose ol{margin:14px 0;padding-left:0}
.prose ul{list-style:none}.prose ul>li{position:relative;padding-left:16px}
.prose ul>li::before{content:'';position:absolute;left:2px;top:.95em;width:5px;height:1px;background:var(--soft)}
.prose ol{padding-left:1.4em}.prose li+li{margin-top:6px}
.prose blockquote{margin:22px 0;padding:2px 0 2px 16px;border-left:2px solid var(--line-2)}
.prose blockquote p{color:var(--fg)}
.prose img{margin:26px auto;border-radius:12px;border:1px solid var(--edge);background:#fff}
.prose hr{border:0;height:1px;margin:32px 0;background:linear-gradient(to right,var(--soft) 1px,transparent 1px) 0 0/4px 1px repeat-x}
.prose table{width:100%;border-collapse:collapse;margin:20px 0;font-size:14px}
.prose td,.prose th{border-bottom:1px dashed var(--line);padding:8px 6px;text-align:left}
.prose .ref p,.prose .ref li{font-size:13.5px;color:var(--muted);line-height:1.7}
.prose .ref a{word-break:break-all;color:var(--muted)}
.y-pn{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:22px var(--pad) 34px}
.y-pn a{display:block;padding:14px 16px;border-radius:12px;border:1px solid var(--edge);background:var(--card);transition:border-color .2s}
.y-pn a:hover{border-color:var(--line-2)}
.y-pn .k{display:block;font:11px/1 var(--mono);color:var(--soft);margin-bottom:8px}
.y-pn b{font-weight:500;font-size:14.5px;line-height:1.5}
.y-pn .n{text-align:right;grid-column:2}
html.dark .prose img{opacity:.92}
@media(max-width:560px){.y-hero .name{font-size:34px}.y-art-head h1{font-size:26px}.prose{font-size:15.5px}.y-pn{grid-template-columns:1fr}.y-pn .n{grid-column:1}}
"""


def cmd_web():
    import shutil, markdown
    from urllib.parse import unquote
    out = "dist/web"
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out + "/posts"); os.makedirs(out + "/images")
    open(out + "/style.css", "w", encoding="utf-8").write(WEB_CSS)
    ts = topics()
    items = [("写在前面", "book/前言.md", "00")] + [(t["part"], t["path"], t["topic_id"]) for t in ts]
    slug = {os.path.normpath(p): f"jingzhi-{tid}" for _, p, tid in items}
    meta = []
    for part, p, tid in items:
        s = open(p, encoding="utf-8").read()
        s = NAV_RE.sub("", s)
        s = re.sub(r"<!--.*?-->", "", s, flags=re.S).strip()
        title = s.splitlines()[0][2:].strip()
        body = "\n".join(s.splitlines()[1:]).strip()
        first = next((l for l in body.splitlines() if l.strip() and not l.startswith(("#", "!", ">", "|", "-"))), "")
        meta.append((part, p, tid, title, body, re.split(r"(?<=[。！？])", first)[0][:70]))
    def page(title, inner, depth, desc=""):
        r = "../" * depth
        fonts = "https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&family=Instrument+Serif:ital@0;1&display=swap"
        nav = (f'<header class="nav wide-line"><a href="/" class="nav-mark" aria-label="pkusi.com">d.</a><nav class="nav-right">'
               f'<a class="nav-link" href="{r}index.html">目录</a><a class="nav-link" href="https://github.com/chuxainpei/how-to-be-yuppie" target="_blank" rel="noopener">github</a>'
               f'<span class="nav-sep" aria-hidden="true"></span><button type="button" class="icon-btn" id="theme-btn" aria-label="切换深浅色">'
               f'<svg class="icon" viewBox="0 0 24 24"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg></button></nav></header>')
        foot = '<div class="band" aria-hidden="true"></div><footer class="foot-base"><span>dan · <a href="/">pkusi.com</a></span><span>精致大学生的第0课</span></footer>'
        js = ('<script>(function(){var t=document.documentElement;try{if(localStorage.getItem("theme")==="dark")t.classList.add("dark")}catch(e){}'
              'document.addEventListener("DOMContentLoaded",function(){var b=document.getElementById("theme-btn");b&&b.addEventListener("click",function(){var d=t.classList.toggle("dark");try{localStorage.setItem("theme",d?"dark":"light")}catch(e){}})})})();</script>')
        return (f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
                f'<title>{html.escape(title)}</title><meta name="description" content="{html.escape(desc)}"><meta name="theme-color" content="#fdfdfc">'
                f'<link rel="icon" href="/favicon.ico" sizes="any">{js}'
                f'<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="{fonts}">'
                f'<link rel="stylesheet" href="/site.css"><link rel="stylesheet" href="{r}style.css"></head>'
                f'<body><div class="page">{nav}<main>{inner}</main>{foot}</div></body></html>')
    for i, (part, p, tid, title, body, summ) in enumerate(meta):
        def img(m):
            src = os.path.normpath(os.path.join(os.path.dirname(p), unquote(m.group(2))))
            if os.path.exists(src):
                shutil.copy(src, f"{out}/images/{os.path.basename(src)}")
                return f"![{m.group(1)}](../images/{os.path.basename(src)})"
            return ""
        b = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", img, body)
        def lk(m):
            u = unquote(m.group(2))
            if re.match(r"^(https?:|mailto:|#)", u): return m.group(0)
            tgt = os.path.normpath(os.path.join(os.path.dirname(p), u.split("#")[0]))
            return f"[{m.group(1)}]({slug[tgt]}.html)" if tgt in slug else m.group(1)
        b = re.sub(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)", lk, b)
        main, _, ref = b.partition("\n## 参考")
        h = markdown.markdown(main, extensions=["tables", "sane_lists"])
        if ref.strip():
            h += '<h2>参考</h2><div class="ref">' + markdown.markdown(ref, extensions=["sane_lists"]) + "</div>"
        h = h.replace("<a href=\"http", "<a target=\"_blank\" rel=\"noopener\" href=\"http")
        prev = meta[i-1] if i > 0 else None
        nxt = meta[i+1] if i + 1 < len(meta) else None
        pn = '<div class="band" aria-hidden="true"></div><nav class="y-pn">'
        pn += f'<a href="jingzhi-{prev[2]}.html"><span class="k">← 上一篇</span><b>{html.escape(prev[3])}</b></a>' if prev else '<a href="../index.html"><span class="k">← 回到</span><b>目录</b></a>'
        pn += f'<a class="n" href="jingzhi-{nxt[2]}.html"><span class="k">下一篇 →</span><b>{html.escape(nxt[3])}</b></a>' if nxt else '<a class="n" href="../index.html"><span class="k">读完了 →</span><b>回到目录</b></a>'
        pn += "</nav>"
        kk = "写在前面" if tid == "00" else f"{tid} · {part}"
        top = f'<header class="y-art-head wide-line"><div class="k">{html.escape(kk)}</div><h1>{html.escape(title)}</h1></header>'
        h = f'<div class="sec-body prose">{h}</div>'
        open(f"{out}/posts/jingzhi-{tid}.html", "w", encoding="utf-8").write(page(title + " · 精致大学生的第0课", top + h + pn, 1, summ))
    pdf = "dist/精致大学生的第0课.pdf"
    has_pdf = os.path.exists(pdf)
    if has_pdf: shutil.copy(pdf, f"{out}/精致大学生的第0课.pdf")
    idx = ['<section class="y-hero"><h1 class="name"><span class="zh">精致大学生的第0课</span></h1>'
           '<p class="role">how to be a yuppie · 25 篇 · 学长经验分享</p>'
           '<p class="lede">给刚来大城市的你：先把自己收拾体面，再大大方方走进那些看起来有点贵的地方。</p>'
           '<div class="y-links"><a class="y-pill" href="posts/jingzhi-00.html">从前言开始读</a>'
           + ('<a class="y-pill" href="精致大学生的第0课.pdf">下载 PDF</a>' if has_pdf else '')
           + '<a class="y-pill" href="https://github.com/chuxainpei/how-to-be-yuppie" target="_blank" rel="noopener">GitHub</a></div></section>']
    groups = []
    for m in meta[1:]:
        if not groups or groups[-1][0] != m[0]: groups.append((m[0], []))
        groups[-1][1].append(m)
    for part, ms in groups:
        rng = f"{ms[0][2]}–{ms[-1][2]}"
        idx.append(f'<div class="band" aria-hidden="true"></div><section class="sec"><header class="sec-head wide-line"><h2>{html.escape(part)}</h2><span class="sec-meta">{rng}</span></header><div class="sec-body"><div class="y-toc">')
        for _, p, tid, title, body, summ in ms:
            idx.append(f'<a href="posts/jingzhi-{tid}.html"><span class="k">{tid}</span><span><b>{html.escape(title)}</b><span class="s">{html.escape(summ)}</span></span></a>')
        idx.append("</div></div></section>")
    open(f"{out}/index.html", "w", encoding="utf-8").write(page("精致大学生的第0课", "".join(idx), 0, "给刚来大城市的你：把自己收拾体面，再大大方方走进去。"))
    print("web ok", len(meta))

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("figs", "all"):
        import subprocess
        subprocess.run([sys.executable, "tools/figs.py"], check=True, stdout=subprocess.DEVNULL)
        print("figs ok")
    if cmd in ("nav", "all"): cmd_nav()
    if cmd in ("merge", "all"): cmd_merge()
    if cmd in ("tables", "all"): cmd_tables()
    if cmd in ("check", "all"): cmd_check()
    if cmd in ("pdf", "all"): cmd_pdf()
    if cmd in ("site", "all"): cmd_site()
    if cmd in ("web", "all"): cmd_web()
