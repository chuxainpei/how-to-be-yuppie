#!/usr/bin/env python3
"""把 figures/*.yaml 里的图示规格渲染成 PNG（assets/figures/）。

用法：
  python3 tools/figs.py            # 渲染全部
  python3 tools/figs.py figures/V01-账单.yaml   # 渲染单个

原理：YAML → HTML（统一样式）→ WeasyPrint 生成 PDF → PyMuPDF 按内容裁切 → PNG。
所有图都由数据生成，不用 AI 生图；金额与文字来自正文和 data/ 表。

YAML 公共字段：
  type: bill | steps | decision | compare | cards | checklist | scale
  title: 图标题（可省）
  note: 图下方小字（可省，写来源或日期）
各类型字段见 render_* 函数的注释。
"""
import glob, html, os, sys, tempfile
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIRS = [os.path.join(ROOT, "tools", "fonts"), "/workspace/work/fonts"]
OUT = os.path.join(ROOT, "assets", "figures")


def font_css():
    def find(name):
        for d in FONT_DIRS:
            p = os.path.join(d, name)
            if os.path.exists(p):
                return "file://" + p
        return None
    css = ""
    for fam, w, f in [("FS", 400, "NotoSansCJKsc-Regular.otf"), ("FS", 700, "NotoSansCJKsc-Bold.otf")]:
        u = find(f)
        if u:
            css += f"@font-face{{font-family:{fam};font-weight:{w};src:url('{u}');}}\n"
    return css


CSS = """
@page { size: 170mm 800mm; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: FS, 'Noto Sans CJK SC', sans-serif; color: #2b2b2b; font-size: 10.5pt; line-height: 1.5; }
.fig { width: 170mm; padding: 7mm 7mm 6mm; background: #faf7f2; border-radius: 4mm; }
.t { font-weight: 700; font-size: 13pt; margin: 0 0 4mm; color: #1f3b4d; }
.note { margin-top: 4mm; font-size: 8.5pt; color: #7a7a7a; }
.ac { color: #c0563b; }
/* bill */
.bill { background: #fff; border: 1px solid #e6dfd3; border-radius: 3mm; padding: 5mm 6mm; }
.bill .row { display: flex; justify-content: space-between; padding: 1.6mm 0; border-bottom: 1px dashed #e3dccf; }
.bill .row .l small { display: block; color: #8a8a8a; font-size: 8.5pt; }
.bill .row .r { white-space: nowrap; font-weight: 700; margin-left: 4mm; }
.bill .row.minus .r { color: #3d7a5a; }
.bill .row.hidden .l::before { content: "易漏 "; font-size: 7.5pt; color: #fff; background: #c0563b; border-radius: 1mm; padding: 0 1mm; margin-right: 1.5mm; vertical-align: 1px; }
.bill .tot { display: flex; justify-content: space-between; margin-top: 3mm; padding-top: 2mm; border-top: 2px solid #1f3b4d; font-weight: 700; font-size: 12pt; }
.bill .calc { margin-top: 1.5mm; font-size: 9pt; color: #555; text-align: right; }
.bills { display: flex; gap: 4mm; }
.bills .bill { flex: 1; }
.bill h4 { margin: 0 0 2mm; font-size: 10.5pt; color: #1f3b4d; }
/* steps */
.steps { position: relative; }
.step { display: flex; gap: 4mm; margin-bottom: 3.2mm; }
.step .n { flex: 0 0 8mm; height: 8mm; border-radius: 50%; background: #1f3b4d; color: #fff; font-weight: 700; text-align: center; line-height: 8mm; font-size: 10pt; }
.step .b { flex: 1; background: #fff; border: 1px solid #e6dfd3; border-radius: 2.5mm; padding: 2.2mm 3.5mm; }
.step .b b { color: #1f3b4d; }
.step .b .say { margin-top: 1mm; color: #c0563b; font-size: 9.5pt; }
.step .b .tag { float: right; font-size: 8.5pt; color: #8a8a8a; margin-left: 3mm; }
/* decision */
.q { background: #1f3b4d; color: #fff; border-radius: 2.5mm; padding: 2.5mm 4mm; font-weight: 700; text-align: center; margin-bottom: 3mm; }
.br { display: flex; gap: 3mm; }
.br .c { flex: 1; background: #fff; border: 1px solid #e6dfd3; border-top: 4px solid #c0563b; border-radius: 2.5mm; padding: 2.5mm 3mm; font-size: 9.5pt; }
.br .c .if { font-weight: 700; color: #c0563b; margin-bottom: 1mm; }
.br .c .then { font-weight: 700; color: #1f3b4d; margin-top: 1mm; }
.dec + .dec { margin-top: 4mm; }
/* compare / cards */
.grid { display: flex; flex-wrap: wrap; gap: 3mm; }
.card { background: #fff; border: 1px solid #e6dfd3; border-radius: 2.5mm; padding: 3mm 3.5mm; font-size: 9.5pt; }
.card h4 { margin: 0 0 1.2mm; font-size: 10.5pt; color: #1f3b4d; }
.card .k { color: #c0563b; font-weight: 700; font-size: 11pt; margin-bottom: 1mm; }
.card ul { margin: 0; padding-left: 4mm; }
.card li { margin: 0.6mm 0; }
.card .sub { color: #8a8a8a; font-size: 8.5pt; margin-top: 1mm; }
.card img { height: 7mm; max-width: 30mm; object-fit: contain; margin-bottom: 1.5mm; }
/* checklist */
.chk .it { display: flex; gap: 3mm; padding: 1.8mm 0; border-bottom: 1px dashed #e3dccf; }
.chk .it .box { flex: 0 0 4.5mm; height: 4.5mm; border: 1.5px solid #1f3b4d; border-radius: 1mm; margin-top: 1mm; }
.chk .it .x small { display: block; color: #8a8a8a; font-size: 8.5pt; }
/* scale */
.scale .lv { display: flex; gap: 3mm; align-items: stretch; margin-bottom: 2.5mm; }
.scale .bar { flex: 0 0 auto; border-radius: 2mm; background: #1f3b4d; color: #fff; padding: 2mm 3mm; font-weight: 700; font-size: 9.5pt; display: flex; align-items: center; }
.scale .d { flex: 1; background: #fff; border: 1px solid #e6dfd3; border-radius: 2mm; padding: 2mm 3mm; font-size: 9.5pt; }
"""


def e(s):
    """转义并允许 **粗体** 与 `强调色`。"""
    s = html.escape(str(s if s is not None else ""))
    import re
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`(.+?)`", r'<span class="ac">\1</span>', s)
    s = s.replace("\n", "<br>")
    return s


def render_bill(d):
    """bills: [{name, rows: [{label, sub, amount, kind: hidden|minus}], total, calc}] 或单个 rows/total/calc"""
    bills = d.get("bills") or [d]
    out = []
    for b in bills:
        h = '<div class="bill">'
        if b.get("name"):
            h += f"<h4>{e(b['name'])}</h4>"
        for r in b.get("rows", []):
            cls = r.get("kind", "")
            sub = f"<small>{e(r['sub'])}</small>" if r.get("sub") else ""
            amt = r.get("amount", "")
            if isinstance(amt, float):
                amt = f"{amt:,.2f}"
            h += f'<div class="row {cls}"><div class="l">{e(r["label"])}{sub}</div><div class="r">{e(amt)}</div></div>'
        if b.get("total"):
            h += f'<div class="tot"><span>{e(b.get("total_label","合计"))}</span><span>{e(b["total"])}</span></div>'
        if b.get("calc"):
            h += f'<div class="calc">{e(b["calc"])}</div>'
        h += "</div>"
        out.append(h)
    return f'<div class="bills">{"".join(out)}</div>' if len(out) > 1 else out[0]


def render_steps(d):
    """steps: [{title, text, say, tag}]"""
    h = '<div class="steps">'
    for i, s in enumerate(d["steps"], 1):
        tag = f'<span class="tag">{e(s["tag"])}</span>' if s.get("tag") else ""
        say = f'<div class="say">“{e(s["say"])}”</div>' if s.get("say") else ""
        txt = f"<div>{e(s['text'])}</div>" if s.get("text") else ""
        h += f'<div class="step"><div class="n">{e(s.get("n", i))}</div><div class="b">{tag}<b>{e(s["title"])}</b>{txt}{say}</div></div>'
    return h + "</div>"


def render_decision(d):
    """question + branches: [{if, text, then}]；或 decisions: [ {question, branches} ... ]"""
    ds = d.get("decisions") or [d]
    h = ""
    for x in ds:
        h += f'<div class="dec"><div class="q">{e(x["question"])}</div><div class="br">'
        for b in x["branches"]:
            then = f'<div class="then">→ {e(b["then"])}</div>' if b.get("then") else ""
            txt = f"<div>{e(b['text'])}</div>" if b.get("text") else ""
            h += f'<div class="c"><div class="if">{e(b["if"])}</div>{txt}{then}</div>'
        h += "</div></div>"
    return h


def render_cards(d):
    """cards: [{title, key, text, items: [], sub, img}]；cols: 每行几张（默认 2）"""
    cols = int(d.get("cols", 2))
    w = f"calc((100% - {3*(cols-1)}mm) / {cols})"
    h = '<div class="grid">'
    for c in d["cards"]:
        img = ""
        if c.get("img"):
            p = c["img"] if os.path.isabs(c["img"]) else os.path.join(ROOT, c["img"])
            img = f'<img src="file://{p}">'
        key = f'<div class="k">{e(c["key"])}</div>' if c.get("key") else ""
        txt = f"<div>{e(c['text'])}</div>" if c.get("text") else ""
        items = "<ul>" + "".join(f"<li>{e(i)}</li>" for i in c.get("items", [])) + "</ul>" if c.get("items") else ""
        sub = f'<div class="sub">{e(c["sub"])}</div>' if c.get("sub") else ""
        title = f"<h4>{e(c['title'])}</h4>" if c.get("title") else ""
        h += f'<div class="card" style="width:{w}">{img}{title}{key}{txt}{items}{sub}</div>'
    return h + "</div>"


render_compare = render_cards


def render_checklist(d):
    """items: [str 或 {text, sub}]"""
    h = '<div class="chk">'
    for it in d["items"]:
        if isinstance(it, dict):
            t, s = it.get("text"), it.get("sub")
        else:
            t, s = it, None
        sub = f"<small>{e(s)}</small>" if s else ""
        h += f'<div class="it"><div class="box"></div><div class="x">{e(t)}{sub}</div></div>'
    return h + "</div>"


def render_scale(d):
    """levels: [{label, text}]，自上而下；宽度递增呈金字塔感"""
    lv = d["levels"]
    h = '<div class="scale">'
    n = len(lv)
    for i, l in enumerate(lv):
        w = 28 + i * (22 / max(1, n - 1))
        h += f'<div class="lv"><div class="bar" style="width:{w}mm">{e(l["label"])}</div><div class="d">{e(l["text"])}</div></div>'
    return h + "</div>"


def to_html(d):
    body = globals()["render_" + d["type"]](d)
    t = f'<div class="t">{e(d["title"])}</div>' if d.get("title") else ""
    n = ""  # note 字段不再渲染：图上不放来源、日期等内部说明
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{font_css()}{CSS}</style></head><body><div class='fig'>{t}{body}{n}</div></body></html>"


def render(path):
    from weasyprint import HTML
    import fitz
    d = yaml.safe_load(open(path, encoding="utf-8"))
    name = os.path.splitext(os.path.basename(path))[0]
    os.makedirs(OUT, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        pdf = os.path.join(td, "f.pdf")
        HTML(string=to_html(d), base_url=ROOT).write_pdf(pdf)
        doc = fitz.open(pdf)
        pg = doc[0]
        # 内容高度：取所有绘制与文字块的最大 y
        ys = [b[3] for b in pg.get_text("blocks")]
        ys += [dr["rect"].y1 for dr in pg.get_drawings()]
        bottom = min(pg.rect.y1, max(ys) + 2) if ys else pg.rect.y1
        clip = fitz.Rect(0, 0, pg.rect.x1, bottom)
        pix = pg.get_pixmap(dpi=200, clip=clip, alpha=False)
        out = os.path.join(OUT, name + ".png")
        pix.save(out)
        if len(doc) > 1:
            print("WARNING: figure overflowed one page:", path)
    return out


def main():
    paths = sys.argv[1:] or sorted(glob.glob(os.path.join(ROOT, "figures", "*.yaml")))
    for p in paths:
        try:
            print(render(p))
        except Exception as ex:
            print("ERROR", p, ex)
            sys.exit(1)


if __name__ == "__main__":
    main()
