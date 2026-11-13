#!/usr/bin/env python3
"""Portable AI行动π article builder. Python standard library only."""
import argparse
import base64
import hashlib
import html
import json
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.0.1"
MIMES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
         ".gif": "image/gif", ".webp": "image/webp"}
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(image:([A-Za-z0-9_-]+)\)")
TOKEN_RE = re.compile(r"(\*\*.+?\*\*|\*[^*]+\*|\[[^\]]+\]\(https?://[^\s)]+\))")

def fail(message):
    raise ValueError(message)

def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2)

def js_data(value):
    return json.dumps(value, ensure_ascii=False).replace("<", r"\u003c").replace("\u2028", r"\u2028").replace("\u2029", r"\u2029")

def normalize(value):
    return re.sub(r"\s+", "", value)

def plain(value):
    value = re.sub(r"\[([^\]]+)\]\(https?://[^\s)]+\)", r"\1", value)
    return value.replace("**", "").replace("*", "")

def inline(value):
    result = []
    for token in TOKEN_RE.split(value):
        if token.startswith("**") and token.endswith("**"):
            result.append('<strong style="font-weight:700;color:#BDF42B;">' + html.escape(token[2:-2]) + '</strong>')
        elif token.startswith("*") and token.endswith("*"):
            result.append('<em>' + html.escape(token[1:-1]) + '</em>')
        elif re.fullmatch(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", token):
            m = re.fullmatch(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", token)
            result.append('<a style="color:#BDF42B;text-decoration:underline;" href="' + html.escape(m[2], quote=True) + '">' + html.escape(m[1]) + '</a>')
        else:
            escaped = html.escape(token)
            escaped = re.sub(r"\b\d{1,2}:\d{2}[—–-]\d{1,2}:\d{2}\b", lambda m: '<span style="white-space:nowrap;">' + m[0] + '</span>', escaped)
            result.append(escaped)
    return "".join(result)

def p(text, style=""):
    return '<p data-paragraph="1" style="margin:0 0 20px;padding:0;font-size:16px;line-height:1.9;letter-spacing:0.2px;color:#E7EDE7;text-align:left;overflow-wrap:break-word;' + style + '">' + inline(text) + '</p>'

def image_placeholder(item):
    label = f'图片占位 {item["number"]:02d}'
    return (f'<section data-image-placeholder="{item["number"]}" style="margin:0;padding:22px 16px;border:1px dashed #BDF42B;border-radius:5px;background-color:#17271E;overflow-wrap:anywhere;">'
            + '<p style="margin:0 0 12px;color:#BDF42B;font-size:17px;font-weight:700;">' + label + '</p>'
            + '<p style="margin:0 0 12px;color:#E7EDE7;font-size:15px;line-height:1.8;">图片内容：' + html.escape(item["alt"]) + '</p>'
            + '<p style="margin:0;color:#ADBBB1;font-size:13px;line-height:1.8;">对应文件：' + html.escape(item["filename"]) + '</p></section>')

def image_valid(data, suffix):
    if suffix in (".jpg", ".jpeg"): return data.startswith(b"\xff\xd8\xff")
    if suffix == ".png": return data.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix == ".gif": return data.startswith((b"GIF87a", b"GIF89a"))
    if suffix == ".webp": return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False

def fingerprint(folder, names):
    h = hashlib.sha256()
    for name in sorted(names):
        h.update(name.encode("utf-8"))
        h.update(b"\0")
        h.update((folder / name).read_bytes())
        h.update(b"\0")
    return h.hexdigest()

def build(args):
    article_path = Path(args.article).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    if out.exists(): fail("输出目录已经存在，请使用新版本目录，保留旧成品。")
    raw = article_path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip()
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    if config.get("schema_version") != 1 or not isinstance(config.get("images"), list):
        fail("配置需要 schema_version: 1 和 images 列表。")
    blocks = re.split(r"\n\s*\n", raw)
    if len(blocks) < 3 or not re.fullmatch(r"# [^\n]+", blocks[0]):
        fail("第一段应是唯一的 # 文章标题，并包含摘要及正文。")
    title = blocks[0][2:].strip()
    prefix = "**摘要：** "
    if not blocks[1].startswith(prefix): fail("第二段请写 **摘要：** 摘要内容。")
    summary = blocks[1][len(prefix):].strip()
    if not summary: fail("摘要不能为空。")
    title_lines = config.get("title_lines", [title])
    if not isinstance(title_lines, list) or not title_lines or any(not isinstance(x, str) or not x.strip() for x in title_lines):
        fail("title_lines 应为非空文字列表。")
    if normalize("".join(title_lines)) != normalize(title): fail("首屏分行标题与文章标题不一致。")
    selected, unused, all_ids = {}, [], set()
    for item in config["images"]:
        ident = item.get("id", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", ident) or ident in all_ids:
            fail("图片 ID 必须唯一，且仅含字母、数字、下划线或连字符。")
        all_ids.add(ident)
        if not isinstance(item.get("use"), bool): fail("每张图都需要布尔值 use。")
        if not item["use"]:
            if not item.get("reason", "").strip(): fail("未使用的图片须填写 reason：" + ident)
            unused.append({"id": ident, "reason": item["reason"]})
            continue
        for key in ["path", "alt", "caption", "kind"]:
            if not isinstance(item.get(key), str) or not item[key].strip():
                fail("使用的图片缺少 " + key + "：" + ident)
        if item["kind"] not in ["photo", "poster", "illustration"]:
            fail("图片 kind 只能是 photo / poster / illustration。")
        source = Path(item["path"]).expanduser()
        if not source.is_absolute(): source = config_path.parent / source
        suffix = source.suffix.lower()
        if suffix not in MIMES or not source.is_file(): fail("图片缺失或格式不支持：" + ident)
        data = source.read_bytes()
        if not image_valid(data, suffix): fail("图片内容与扩展名不符：" + ident)
        selected[ident] = {**item, "_data": data, "_suffix": suffix}
    refs = [m[2] for block in blocks[2:] if (m := IMAGE_RE.fullmatch(block))]
    if len(refs) != len(set(refs)): fail("同一图片被重复引用，请明确保留一个位置。")
    if set(refs) != set(selected):
        fail("图片清单与正文不一致；漏放=" + ",".join(sorted(set(selected) - set(refs))) +
             "；未登记/未选却引用=" + ",".join(sorted(set(refs) - set(selected))))
    manifest, output_images = [], {}
    for number, ident in enumerate(refs, 1):
        item = selected[ident]
        name = f"{number:02d}_{ident}{item['_suffix']}"
        output_images["配图/" + name] = item["_data"]
        manifest.append({"number": number, "id": ident, "filename": name,
                         "kind": item["kind"], "alt": item["alt"], "caption": item["caption"],
                         "sha256": hashlib.sha256(item["_data"]).hexdigest()})
    by_id = {item["id"]: item for item in manifest}
    source_texts, body = [], []
    section_count = 0
    for block in blocks[2:]:
        image_match = IMAGE_RE.fullmatch(block)
        if image_match:
            item = by_id[image_match[2]]
            body.append('<section style="margin:26px 0 28px;padding:8px 8px 11px;background-color:#1A2B23;border-radius:7px;">'
                        + f'<img data-image-number="{item["number"]}" src="@@IMAGE_{item["number"]}@@" alt="{html.escape(item["alt"], quote=True)}" style="display:block;width:100%;max-width:100%;height:auto;margin:0;border:0;">'
                        + '<p style="margin:10px 6px 0;font-size:12px;line-height:1.8;text-align:center;color:#ADBBB1;">'
                        + html.escape(item["caption"]) + '</p></section>')
            source_texts.append(item["caption"])
            continue
        if "![" in block or re.search(r"<[A-Za-z/!]", block) or block.startswith((chr(96)*3, "~~~", "|", "# ", "#####", "* ")):
            fail("有不支持的 Markdown 或未独占一段的图片，请调整：" + block[:50])
        if re.search(r"\n[ \t]+(?:[-*] |\d+\. )", block):
            fail("暂不支持嵌套列表，请改为简单清单。")
        if block.startswith(("## ", "### ", "#### ")):
            m = re.fullmatch(r"(#{2,4}) ([^\n]+)", block)
            if not m: fail("标题需要独占一段。")
            level, text = len(m[1]), m[2]
            if level == 2:
                text = re.sub(r"^\d+\s*[｜|]\s*", "", text)
            source_texts.append(plain(text))
            if level == 2:
                section_count += 1
                body.append(f'<section style="margin:36px 0 24px;padding-top:22px;border-top:1px solid #30473A;"><p style="margin:0 0 10px;color:#BDF42B;font-size:12px;letter-spacing:2px;font-weight:700;">{section_count:02d} / AI行动π</p><h2 style="margin:0;font-size:22px;line-height:1.55;color:#F2F5ED;">{inline(text)}</h2></section>')
            elif level == 3:
                body.append('<h3 style="margin:28px 0 16px;padding:12px 14px;background-color:#1A2B23;border-left:2px solid #BDF42B;font-size:19px;line-height:1.6;color:#F2F5ED;">' + inline(text) + '</h3>')
            else:
                body.append('<h4 style="margin:20px 0 14px;font-size:16px;line-height:1.8;color:#ADBBB1;">' + inline(text) + '</h4>')
        elif all(re.match(r"(?:\d+\. |- )", line) for line in block.splitlines()):
            body.append('<section style="margin:18px 0 24px;padding:16px 14px 4px;background-color:#17271E;border-radius:7px;">')
            for index, line in enumerate(block.splitlines(), 1):
                text = re.sub(r"^(?:\d+\. |- )", "", line)
                label = f"{index:02d}" if re.match(r"\d+\.", line) else "·"
                source_texts.append(plain(text))
                body.append('<p data-paragraph="1" style="margin:0 0 12px;padding-left:28px;text-indent:-28px;font-size:16px;line-height:1.85;color:#E7EDE7;"><span style="display:inline-block;width:28px;text-indent:0;font-size:13px;font-weight:700;color:#BDF42B;">' + label + '</span>' + inline(text) + '</p>')
            body.append('</section>')
        elif block.startswith("> "):
            if not all(line.startswith("> ") for line in block.splitlines()): fail("引用每行应以 > 开头。")
            text = " ".join(line[2:] for line in block.splitlines())
            source_texts.append(plain(text))
            body.append(p(text, "padding:8px 0 8px 13px;border-left:2px solid #BDF42B;color:#D9E7D9;"))
        else:
            if re.search(r"\n(?:#{1,4} |[-*] |\d+\. )", block): fail("标题、清单与段落之间需要空白行。")
            text = block.replace("\n", " ")
            source_texts.append(plain(text))
            body.append(p(text))
    content_text = "\n".join([title, summary] + source_texts)
    checks = config.get("checks", {})
    for phrase in checks.get("required_phrases", []):
        if phrase not in content_text: fail("缺少当期要求的文字：" + phrase)
    for phrase in checks.get("forbidden_phrases", []):
        if phrase in content_text: fail("出现当期要求删除的文字：" + phrase)
    kicker = " · ".join(x for x in [config.get("brand", "AI行动π"), config.get("edition", "")] if x)
    hero = '<section style="padding:27px 24px 30px;background-color:#1A271E;border-top:4px solid #BDF42B;">'
    if config.get("demo", False): hero += '<p style="margin:0 0 16px;color:#ADBBB1;font-size:12px;">演示资料 · 不用于实际报名</p>'
    hero += '<p style="margin:0 0 20px;font-size:12px;line-height:1.7;font-weight:600;letter-spacing:1px;color:#BDF42B;">' + html.escape(kicker) + '</p>'
    hero += '<h1 style="margin:0 0 18px;font-size:30px;line-height:1.55;letter-spacing:0;font-weight:700;color:#F2F5ED;">' + '<br>'.join(html.escape(x) for x in title_lines) + '</h1>'
    if config.get("subtitle"): hero += '<p style="margin:0;font-size:14px;line-height:1.8;color:#ADBBB1;">' + html.escape(config["subtitle"]) + '</p>'
    hero += '</section>'
    article = '<section id="article" style="box-sizing:border-box;width:100%;max-width:640px;margin:0 auto;background-color:#0F1410;color:#E7EDE7;font-family:-apple-system,BlinkMacSystemFont,\'PingFang SC\',\'Microsoft YaHei\',sans-serif;font-size:16px;line-height:1.9;">' + hero + '<section style="padding:28px 20px 18px;">' + "\n".join(body) + '</section></section>'
    embedded, linked = article, article
    for item in manifest:
        name = "配图/" + item["filename"]
        data_url = "data:" + MIMES[Path(name).suffix] + ";base64," + base64.b64encode(output_images[name]).decode("ascii")
        marker = f'@@IMAGE_{item["number"]}@@'
        embedded = embedded.replace(marker, data_url)
        linked = linked.replace(marker, quote(name, safe="/"))
    head = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + html.escape(title) + '</title></head>'
    static = head + '<body style="margin:0;background-color:#0F1410;">' + linked + '</body></html>'
    placeholders = [image_placeholder(item) for item in manifest]
    draft_article = re.sub(r'<img data-image-number="(\d+)"[^>]*>', lambda m: placeholders[int(m[1])-1], article)
    draft_html = head + '<body style="margin:0;background-color:#0F1410;">' + draft_article + '</body></html>'
    draft_blocks = []
    for block in blocks:
        match = IMAGE_RE.fullmatch(block)
        if match:
            item = by_id[match[2]]
            draft_blocks.append(f'> **【图片占位 {item["number"]:02d}】**\n>\n> 图片内容：{item["alt"]}\n>\n> 对应文件：配图/{item["filename"]}\n>\n> 图注：{item["caption"]}')
        else:
            draft_blocks.append(block)
    draft_markdown = '\n\n'.join(draft_blocks) + '\n'
    shell = (ROOT / "assets/preview.html").read_text(encoding="utf-8")
    values = {"ARTICLE": embedded, "TITLE_JSON": js_data(title), "SUMMARY_JSON": js_data(summary),
              "FILES_JSON": js_data([x["filename"] for x in manifest]), "PLACEHOLDERS_JSON": js_data(placeholders), "COUNT": str(len(manifest))}
    preview = re.sub(r"@@([A-Z_]+)@@", lambda m: values[m[1]], shell)
    exported_config = {k: config[k] for k in ["schema_version", "brand", "edition", "author", "subtitle", "title_lines", "checks", "demo"] if k in config}
    exported_config["images"] = [{**{k: x[k] for k in ["id", "kind", "alt", "caption"]}, "use": True, "path": "配图/" + x["filename"]} for x in manifest]
    names_text = "\n".join(f'{x["number"]:02d} {x["filename"]}：{x["caption"]}' for x in manifest)
    instructions = f"""公众号排版使用说明（Skill v{VERSION}）

1. 审稿时打开“初稿_图片占位.html”或“初稿_图片占位.md”，正文中直接标明图片位置、内容、对应文件和图注。打开“公众号排版预览.html”可看完整图文，点击“查看图片占位”切换。
2. 复制标题、摘要到公众号对应栏位。
3. 复制正文排版后粘贴到公众号正文编辑器。图片以编号提示保留，请按顺序上传配图目录中的 {len(manifest)} 张图片，并删除提示文字。
4. 通过公众号后台的手机预览检查深色背景、图片和二维码，再按当期授权发布。

{names_text}

“公众号排版预览.html”自带图片，可单独查看。“公众号正文.html”引用旁边的配图文件夹，请一起保留。
“初稿_图片占位.md”供作者阅读和修改；修改后让 Codex 同步到“文章.md”和“本期配置.json”再构建。“文章.md”是排版源文件，不作为给作者阅读的初稿；配图仍须一起保留。
本地检查不等于公众号后台粘贴、上传和手机预览已验证；二维码真实扫码需另行检查。
"""
    out.mkdir(parents=True)
    output = {"文章.md": raw + "\n", "本期配置.json": dump(exported_config), "公众号正文.html": static,
              "公众号排版预览.html": preview, "标题与摘要.txt": f"标题\n{title}\n\n摘要\n{summary}\n",
              "初稿_图片占位.md": draft_markdown, "初稿_图片占位.html": draft_html,
              "使用说明.txt": instructions, "配图清单.json": dump({"images": manifest, "unused": unused})}
    for name, value in output.items(): (out / name).write_text(value, encoding="utf-8")
    for name, data in output_images.items():
        (out / name).parent.mkdir(exist_ok=True)
        (out / name).write_bytes(data)
    fingerprint_files = sorted(list(output) + list(output_images))
    record = {"skill_version": VERSION, "title": title, "summary": summary,
              "expected_title_lines": len(title_lines) if "title_lines" in config else None,
              "images": manifest, "source_texts": source_texts,
              "fingerprint_files": fingerprint_files,
              "fingerprint": fingerprint(out, fingerprint_files)}
    (out / "构建记录.json").write_text(dump(record), encoding="utf-8")
    print(dump({"output": str(out), "images": len(manifest), "status": "built; browser verification pending"}))

def pack(args):
    folder = Path(args.dir).expanduser().resolve()
    record = json.loads((folder / "构建记录.json").read_text(encoding="utf-8"))
    report = json.loads((folder / "检查报告.json").read_text(encoding="utf-8"))
    current = fingerprint(folder, record["fingerprint_files"])
    if not report.get("passed") or current != record["fingerprint"] or current != report.get("fingerprint"):
        fail("检查报告未通过或已过期，请重新构建/检查后打包。")
    names = record["fingerprint_files"] + ["构建记录.json", "检查报告.json", "手机预览.png", "首屏预览.png", "初稿_图片占位.png"]
    if any(not (folder / name).is_file() for name in names): fail("交付文件缺失。")
    destination = folder.with_name(folder.name + "_排版包.zip")
    if destination.exists(): fail("排版包已存在，请保留旧包，改用新版本目录。")
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in names: archive.write(folder / name, (Path(folder.name) / name).as_posix())
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None: fail("ZIP 校验失败。")
    print(dump({"package": str(destination), "files": len(names), "warnings": report.get("warnings", [])}))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build_cmd = commands.add_parser("build")
    for arg in ["article", "config", "out"]: build_cmd.add_argument("--" + arg, required=True)
    pack_cmd = commands.add_parser("pack")
    pack_cmd.add_argument("--dir", required=True)
    args = parser.parse_args()
    try: (build if args.command == "build" else pack)(args)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print("未完成：" + str(exc), file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
