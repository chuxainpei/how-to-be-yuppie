#!/usr/bin/env python3
"""把 index.html、正文、目录和插图打成一个离线单文件：dist/how-to-be-yuppie.html
双击就能开，不用联网也不用服务器。用法：python3 tools/offline.py"""
import base64, csv, json, mimetypes, os, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
rows = list(csv.DictReader(open("data/topics.tsv", encoding="utf-8"), delimiter="\t"))
paths = ["book/前言.md"] + [r["path"] for r in rows]
files = {"data/topics.tsv": open("data/topics.tsv", encoding="utf-8").read()}
images = {}
for p in paths:
    t = open(p, encoding="utf-8").read()
    files[p] = t
    for src in re.findall(r"!\[[^\]]*\]\(([^)\s]+)", t):
        if src.startswith(("http:", "https:", "data:")):
            continue
        ip = os.path.normpath(os.path.join(os.path.dirname(p), src)).replace(os.sep, "/")
        if os.path.exists(ip):
            mt = mimetypes.guess_type(ip)[0] or "image/png"
            images[ip] = f"data:{mt};base64," + base64.b64encode(open(ip, "rb").read()).decode()
html = open("index.html", encoding="utf-8").read()
marked = open("vendor/marked.min.js", encoding="utf-8").read()
data = json.dumps({"files": files, "images": images}, ensure_ascii=False).replace("</", "<\\/")
html = html.replace('<script src="vendor/marked.min.js"></script>',
                    f"<script>{marked}</script>\n<script>window.BOOK={data};</script>")
os.makedirs("dist", exist_ok=True)
out = "dist/how-to-be-yuppie.html"
open(out, "w", encoding="utf-8").write(html)
print("offline ok", out, f"{os.path.getsize(out)/1e6:.1f} MB", len(files) - 1, "篇", len(images), "图")
