#!/usr/bin/env python3
"""Render a self-contained, human-readable HTML view of a Markdown package.

This renderer intentionally uses only the Python standard library. It supports
the subset used by the framework: headings, paragraphs, block quotes, lists,
tables, fenced code, links, inline code, emphasis, and local image references.
The Markdown file remains the primary fact source; the HTML file is derived.
"""

from __future__ import annotations

import argparse
import html
import hashlib
import json
from urllib.parse import urlsplit
import re
from pathlib import Path
from package_versions import SUPPORTED_CURRENT_VERSIONS


META_RE = re.compile(r"<!--\s*predev-meta:\s*([^>]+?)\s*-->")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
IMAGE_RE = re.compile(r'^!\[([^]]*)\]\(([^ )]+)(?:\s+"([^"]*)")?\)\s*$')
LIST_RE = re.compile(r"^\s*[-*]\s+(.+)$")
ORDERED_RE = re.compile(r"^\s*\d+[.)]\s+(.+)$")


def slugify(text: str, index: int) -> str:
    clean = re.sub(r"`([^`]*)`", r"\1", text)
    clean = re.sub(r"[^\w\u4e00-\u9fff]+", "-", clean, flags=re.UNICODE).strip("-").lower()
    return clean or f"section-{index}"


def safe_url(value: str) -> str:
    decoded = html.unescape(value).strip()
    if any(ord(char) < 32 for char in decoded): return '#'
    try:
        if urlsplit(decoded).scheme.lower() not in {'', 'http', 'https', 'mailto'}: return '#'
    except ValueError:
        return '#'
    return html.escape(decoded, quote=True)


def render_inline(text: str) -> str:
    code_values: list[str] = []

    def store_code(match: re.Match[str]) -> str:
        code_values.append(f"<code>{html.escape(match.group(1))}</code>")
        return f"@@CODE{len(code_values) - 1}@@"

    text = re.sub(r"`([^`]+)`", store_code, text)
    text = html.escape(text, quote=False)

    def store_image(match: re.Match[str]) -> str:
        alt, target, title = match.groups()
        title_attr = f' title="{html.escape(html.unescape(title), quote=True)}"' if title else ''
        code_values.append(
            f'<a href="{safe_url(target)}"><img src="{safe_url(target)}" '
            f'alt="{html.escape(html.unescape(alt), quote=True)}"{title_attr}></a>'
        )
        return f"@@CODE{len(code_values) - 1}@@"

    text = re.sub(r'!\[([^]]*)\]\(([^ )]+)(?:\s+"([^"]*)")?\)', store_image, text)
    text = re.sub(
        r"\[([^]]+)\]\(([^)]+)\)",
        lambda match: (
            f'<a href="{safe_url(match.group(2))}">'
            f"{match.group(1)}</a>"
        ),
        text,
    )
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    for index, value in enumerate(code_values):
        text = text.replace(f"@@CODE{index}@@", value)
    return text


def split_table_row(line: str) -> list[str]:
    # Keep escaped pipes and pipes inside code spans in the same table cell.
    value = line.strip()
    if value.startswith("|"): value = value[1:]
    if value.endswith("|") and not value.endswith("\\|"): value = value[:-1]
    cells, current, code_ticks = [], [], 0
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\" and index + 1 < len(value) and value[index + 1] == "|":
            current.append("|")
            index += 2
            continue
        if char == "`":
            end = index
            while end < len(value) and value[end] == "`": end += 1
            run = end - index
            if not code_ticks: code_ticks = run
            elif code_ticks == run: code_ticks = 0
            current.append(value[index:end])
            index = end
            continue
        if char == "|" and not code_ticks:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    cells.append("".join(current).strip())
    return cells


def is_table_separator(line: str) -> bool:
    cells = split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def is_block_start(lines: list[str], index: int) -> bool:
    line = lines[index]
    if not line.strip():
        return True
    if HEADING_RE.match(line) or line.startswith("```") or line.startswith(">"):
        return True
    if LIST_RE.match(line) or ORDERED_RE.match(line) or IMAGE_RE.match(line.strip()):
        return True
    if line.strip().startswith("|") and index + 1 < len(lines) and is_table_separator(lines[index + 1]):
        return True
    return False


def render_markdown(source: str) -> tuple[str, list[tuple[int, str, str]]]:
    lines = source.splitlines()
    output: list[str] = []
    headings: list[tuple[int, str, str]] = []
    index = 0
    heading_index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped or META_RE.search(line):
            index += 1
            continue

        heading_match = HEADING_RE.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2)
            heading_index += 1
            anchor = slugify(title, heading_index)
            headings.append((level, re.sub(r"`", "", title), anchor))
            output.append(f'<h{level} id="{anchor}">{render_inline(title)}</h{level}>')
            index += 1
            continue

        if line.startswith("```"):
            language = line[3:].strip()
            block: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                block.append(lines[index])
                index += 1
            index += 1 if index < len(lines) else 0
            rendered_code = (
                f'<pre><code class="language-{html.escape(language, quote=True)}">'
                f'{html.escape(chr(10).join(block))}</code></pre>'
            )
            if language == "mermaid":
                output.append(
                    '<details class="diagram-source"><summary>查看 Mermaid 图源码</summary>'
                    f"{rendered_code}</details>"
                )
            else:
                output.append(rendered_code)
            continue

        image_match = IMAGE_RE.match(stripped)
        if image_match:
            alt, target, title = image_match.groups()
            caption = title or alt
            output.append(
                '<figure class="diagram">'
                f'<a href="{safe_url(target)}">'
                f'<img src="{safe_url(target)}" alt="{html.escape(alt, quote=True)}"></a>'
                f'<figcaption>{render_inline(caption)}</figcaption>'
                '</figure>'
            )
            index += 1
            continue

        if stripped.startswith("|") and index + 1 < len(lines) and is_table_separator(lines[index + 1]):
            headers = split_table_row(line)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(split_table_row(lines[index]))
                index += 1
            output.append('<div class="table-wrap"><table><thead><tr>')
            output.extend(f"<th>{render_inline(cell)}</th>" for cell in headers)
            output.append("</tr></thead><tbody>")
            for row in rows:
                output.append("<tr>")
                padded = row + [""] * max(0, len(headers) - len(row))
                output.extend(f"<td>{render_inline(cell)}</td>" for cell in padded[: len(headers)])
                output.append("</tr>")
            output.append("</tbody></table></div>")
            continue

        if line.startswith(">"):
            quote_lines: list[str] = []
            while index < len(lines) and lines[index].startswith(">"):
                quote_lines.append(lines[index].lstrip("> "))
                index += 1
            output.append(f"<blockquote>{render_inline(' '.join(quote_lines))}</blockquote>")
            continue

        list_match = LIST_RE.match(line)
        if list_match:
            items: list[str] = []
            while index < len(lines):
                match = LIST_RE.match(lines[index])
                if not match:
                    break
                items.append(match.group(1))
                index += 1
            output.append("<ul>" + "".join(f"<li>{render_inline(item)}</li>" for item in items) + "</ul>")
            continue

        ordered_match = ORDERED_RE.match(line)
        if ordered_match:
            items = []
            while index < len(lines):
                match = ORDERED_RE.match(lines[index])
                if not match:
                    break
                items.append(match.group(1))
                index += 1
            output.append("<ol>" + "".join(f"<li>{render_inline(item)}</li>" for item in items) + "</ol>")
            continue

        paragraph = [stripped]
        index += 1
        while index < len(lines) and not is_block_start(lines, index):
            paragraph.append(lines[index].strip())
            index += 1
        output.append(f"<p>{render_inline(' '.join(paragraph))}</p>")

    return "\n".join(output), headings


def package_inputs(source_path: Path):
    manifest_path = source_path.parent / 'package-manifest.json'
    if not manifest_path.is_file(): return None, {}
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('framework_version') not in SUPPORTED_CURRENT_VERSIONS: return None, {}
    files = {'package-manifest.json': manifest_path}
    root = source_path.parent.resolve()
    for raw in manifest['artifacts']:
        if raw == manifest.get('readable_artifact'): continue
        if not raw or '\\' in raw or ':' in raw or '..' in Path(raw).parts or Path(raw).is_absolute():
            raise ValueError('unsafe package artifact path')
        path = (root / raw).resolve()
        if not path.is_relative_to(root) or path == root:
            raise ValueError('package artifact escapes source directory')
        files[raw] = path
    return manifest, files


def package_fingerprint(source_path: Path, markdown: str) -> str:
    _, files = package_inputs(source_path)
    digest = hashlib.sha256(markdown.encode('utf-8'))
    for name, path in sorted(files.items()):
        digest.update(name.encode('utf-8') + b'\0' + hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def render_plan(source_path: Path) -> str:
    manifest, files = package_inputs(source_path)
    if manifest is None: return ''
    plan = json.loads(files[manifest['plan_artifact']].read_text(encoding='utf-8'))
    labels = dict(id='标识', statement='需求行为', source_ids='来源', acceptance_ids='验收',
                  criterion='验收标准', method='验证方式', owner='负责人', state='状态',
                  definition='契约定义', evidence='证据', title='名称', objective='目标',
                  scope='范围', non_goals='非目标', requirements='需求', contracts='契约',
                  depends_on='前置任务', responsibility='已确认职责', collaborators='协作者',
                  slice_id='所属切片', task_ids='任务', readiness='材料就绪度', blockers='阻塞',
                  conditions='条件', authorized='已授权', approval='批准记录',
                  integration_owner='联调负责人', acceptance_owner='验收负责人',
                  kind='变更类型', before='原语义', after='新语义', affected_tasks='影响任务',
                  approved_by='批准人', approved_at='批准时间', approved_package_version='批准包版本',
                  decision_by='最迟决策点', isolation='隔离理由', invalidated_tasks='失效任务',
                  high_consequence='高后果未决项')
    def value(item):
        if isinstance(item, bool): return '是' if item else '否'
        if isinstance(item, list):
            return '<ul>' + ''.join('<li>' + value(x) + '</li>' for x in item) + '</ul>' if item else '无'
        if isinstance(item, dict):
            return '<dl>' + ''.join('<dt>' + html.escape(labels.get(k,k)) + '</dt><dd>' + value(v) + '</dd>' for k,v in item.items()) + '</dl>'
        return html.escape(str(item))
    def table(fields, rows):
        headers = ''.join('<th>' + html.escape(labels.get(field,field)) + '</th>' for field in fields)
        body = ''.join('<tr>' + ''.join('<td>' + value(row.get(field, '')) + '</td>' for field in fields) + '</tr>' for row in rows)
        return '<div class="table-wrap"><table><thead><tr>' + headers + '</tr></thead><tbody>' + body + '</tbody></table></div>'
    result = '<h2 id="structured-plan">结构化交付映射（由 delivery-plan.json 派生）</h2>'
    for key, title in [('requirements','需求'), ('acceptance','验收'), ('contracts','契约'), ('tasks','任务'), ('slices','切片与授权'), ('changes','变化')]:
        rows = plan[key]
        if not rows: continue
        result += '<h3>' + title + '</h3>'
        if key in {'tasks','slices'}:
            for row in rows:
                result += '<h4>' + html.escape(row['id'] + ' ' + row.get('title','')) + '</h4>'
                result += '<div class="table-wrap"><table><thead><tr><th>字段</th><th>内容</th></tr></thead><tbody>'
                result += ''.join('<tr><td>' + html.escape(labels.get(k,k)) + '</td><td>' + value(v) + '</td></tr>' for k,v in row.items() if k not in {'id','title'})
                result += '</tbody></table></div>'
        else:
            fields = list(dict.fromkeys(field for row in rows for field in row))
            result += table(fields, rows)
    return result


def build_html(source_path: Path, markdown: str, title_override: str = "") -> str:
    content, headings = render_markdown(markdown)
    plan_content = render_plan(source_path)
    content += plan_content
    if plan_content:
        headings.append((2, "结构化交付映射", "structured-plan"))
    fingerprint = package_fingerprint(source_path, markdown)
    title_match = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
    manifest, _ = package_inputs(source_path)
    title = (manifest or {}).get('readable_title') or (title_match.group(1) if title_match else source_path.stem)
    if title_override:
        if manifest is not None and title_override != title:
            raise ValueError('package title override must be recorded in manifest readable_title before rendering')
        title = title_override
    meta_match = META_RE.search(markdown)
    meta_comment = f"<!-- predev-meta: {meta_match.group(1)} -->" if meta_match else ""
    nav_items = []
    for level, label, anchor in headings:
        if level in {2, 3}:
            nav_items.append(
                f'<li class="level-{level}"><a href="#{anchor}">{html.escape(label)}</a></li>'
            )
    navigation = "\n".join(nav_items)
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src 'self' file: data: https: http:; base-uri 'none'; form-action 'none'">
  <title>{html.escape(title)}</title>
  {meta_comment}
  <!-- predev-derived-from: {html.escape(source_path.name)} -->
  <!-- predev-source-sha256: {fingerprint} -->
  <style>
    :root {{ color-scheme: light dark; --bg:#f5f7fb; --paper:#fff; --text:#172033; --muted:#64748b; --line:#dbe3ef; --head:#eef4ff; --accent:#2563eb; --warn-bg:#fff7df; --warn-line:#f59e0b; --code:#eef2f7; }}
    * {{ box-sizing:border-box; }}
    html {{ scroll-behavior:smooth; }}
    body {{ margin:0; background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif; line-height:1.72; }}
    .shell {{ display:grid; grid-template-columns:280px minmax(0,1fr); max-width:1680px; margin:0 auto; }}
    .toc {{ position:sticky; top:0; align-self:start; height:100vh; overflow:auto; padding:28px 22px; border-right:1px solid var(--line); background:var(--paper); }}
    .toc strong {{ display:block; margin-bottom:12px; }}
    .toc ul {{ list-style:none; padding:0; margin:0; }}
    .toc li {{ margin:3px 0; }}
    .toc .level-3 {{ padding-left:14px; font-size:13px; }}
    .toc a {{ color:var(--muted); text-decoration:none; }}
    .toc a:hover {{ color:var(--accent); }}
    main {{ min-width:0; margin:28px; padding:48px 54px 80px; background:var(--paper); border:1px solid var(--line); border-radius:16px; box-shadow:0 12px 34px rgba(15,23,42,.06); }}
    h1 {{ margin:0 0 26px; font-size:32px; line-height:1.25; }}
    h2 {{ margin:58px 0 18px; padding-bottom:10px; border-bottom:2px solid var(--line); font-size:25px; }}
    h3 {{ margin:36px 0 14px; font-size:20px; }}
    h4 {{ margin:26px 0 10px; font-size:17px; }}
    p {{ margin:10px 0; }}
    a {{ color:var(--accent); }}
    main img {{ max-width:100%; height:auto; }}
    code {{ padding:2px 6px; border-radius:5px; background:var(--code); font-family:"SFMono-Regular",Consolas,monospace; font-size:.9em; }}
    pre {{ overflow:auto; padding:18px; border:1px solid var(--line); border-radius:10px; background:var(--code); }}
    pre code {{ padding:0; background:transparent; }}
    blockquote {{ margin:18px 0; padding:14px 18px; border-left:4px solid var(--warn-line); background:var(--warn-bg); border-radius:0 8px 8px 0; }}
    ul,ol {{ padding-left:26px; }}
    li {{ margin:4px 0; }}
    .table-wrap {{ width:100%; margin:18px 0 28px; overflow-x:auto; border:1px solid var(--line); border-radius:10px; }}
    table {{ width:100%; border-collapse:separate; border-spacing:0; font-size:14px; line-height:1.55; }}
    th {{ position:sticky; top:0; padding:11px 12px; text-align:left; vertical-align:top; background:var(--head); border-bottom:1px solid var(--line); white-space:nowrap; }}
    td {{ min-width:108px; padding:11px 12px; vertical-align:top; border-bottom:1px solid var(--line); }}
    tr:last-child td {{ border-bottom:0; }}
    tbody tr:nth-child(even) {{ background:color-mix(in srgb,var(--head) 35%,transparent); }}
    .diagram {{ margin:24px 0 34px; padding:16px; border:1px solid var(--line); border-radius:12px; background:#fff; }}
    .diagram a {{ display:block; }}
    .diagram img {{ display:block; width:100%; height:auto; max-height:900px; object-fit:contain; }}
    figcaption {{ margin-top:10px; color:#475569; text-align:center; font-size:14px; }}
    .diagram-source {{ margin:-22px 0 30px; color:var(--muted); font-size:13px; }}
    .diagram-source summary {{ cursor:pointer; user-select:none; }}
    .diagram-source pre {{ margin-top:8px; }}
    @media (prefers-color-scheme:dark) {{
      :root {{ --bg:#0f172a; --paper:#111c30; --text:#e5edf8; --muted:#a7b4c7; --line:#30405a; --head:#192b49; --accent:#7db2ff; --warn-bg:#3a2d12; --warn-line:#fbbf24; --code:#1d293d; }}
      .diagram {{ background:#fff; }}
      tbody tr:nth-child(even) {{ background:#15223a; }}
    }}
    @media (max-width:980px) {{ .shell {{ display:block; }} .toc {{ position:relative; height:auto; border-right:0; border-bottom:1px solid var(--line); }} main {{ margin:12px; padding:28px 20px 60px; }} h1 {{ font-size:27px; }} h2 {{ font-size:22px; }} }}
    @media print {{ body {{ background:#fff; }} .shell {{ display:block; max-width:none; }} .toc {{ display:none; }} main {{ margin:0; padding:0; border:0; box-shadow:none; }} .table-wrap {{ overflow:visible; }} table {{ font-size:10px; }} .diagram {{ break-inside:avoid; }} }}
  </style>
</head>
<body>
  <div class="shell">
    <nav class="toc" aria-label="目录"><strong>文档目录</strong><ul>{navigation}</ul></nav>
    <main>{content}</main>
  </div>
</body>
</html>
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--title", default="")
    args = parser.parse_args()

    source_path = Path(args.source).resolve()
    output_path = Path(args.output).resolve()
    if source_path.suffix.lower() != ".md":
        parser.error("source must use .md")
    if output_path.parent != source_path.parent:
        parser.error("output must be beside source Markdown")
    if not source_path.is_file():
        parser.error(f"source does not exist: {source_path}")
    try:
        output_path.relative_to(source_path.parent)
    except ValueError:
        parser.error("output must remain inside the source package directory")
    if output_path.suffix.lower() != ".html":
        parser.error("output must use .html")

    markdown = source_path.read_text(encoding="utf-8")
    try:
        rendered = build_html(source_path, markdown, args.title)
        output_path.write_text(rendered, encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Cannot render package: {exc}\n")
    print(f"READABLE PACKAGE RENDERED: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
