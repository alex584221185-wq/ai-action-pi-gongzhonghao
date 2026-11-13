# 输入格式与操作

## 作者使用

每位作者在自己的电脑安装同一 Skill，各期另建文件夹。复制 `assets/本期资料模板.md` 填写，或直接向 Codex 提供信息与素材。Codex 整理文稿和配置后运行工具。

运行位置不限。素材路径相对于本期 JSON 配置文件解析；也支持用户提供的本机绝对路径。安装包中不预置任何人的本地路径。图片路径用正斜杠可跨系统复用。

## 阅读初稿与排版源文件

给作者看初稿时，优先提供“初稿_图片占位.md”或“初稿_图片占位.html”。每处占位直接说明图片内容、对应文件和图注。尚未选定图片时，由 Codex 在写稿阶段先写出所需画面并标记“素材待补”；正式图文构建仍需补齐已选素材。

“公众号排版预览.html”可通过“查看图片占位 / 查看配图效果”切换；两种模式下复制正文只保留一套图片编号提示。作者修改阅读稿后，由 Codex 同步到排版源文件再生成成品。

## 文章格式

第一段是唯一的 `# 文章标题`；第二段为 `**摘要：** 摘要内容`。每段以空白行分隔。正文支持段落、`##` / `###` / `####` 标题、`**加粗**`、`*斜体*`、`[链接](https://...)`、`>` 引用、简单编号或无序列表。

二级标题会自动编号；已有“01｜”或“01 |”前缀时自动去重。

图片独占一段：`![简短描述](image:scene)`；scene 对应配置中的图片 ID，图注以配置为准。表格、嵌套清单、原始 HTML、代码围栏暂不支持；请改成普通段落/清单，不让脚本静默吞掉。

## 本期配置

参见 `examples/demo/issue.json`。必填 schema_version: 1、images。`title_lines` 指定首屏每行；合并后须与 Markdown 标题相同（忽略空白）。未提供时标题自然换行。

- brand：默认 AI行动π。
- edition：本期名称；不预设期数。
- author：当期执笔人，只保存在配置，不自动显示在正文。
- subtitle：首屏辅助信息；活动时间未知时不填。
- demo：演示资料设 true；预览及正文首屏显示演示标识。
- checks.required_phrases / checks.forbidden_phrases：本期要求检查的短语；无要求可省略。
- images：每项含唯一 id、path、kind（photo / poster / illustration）、alt、caption、布尔值 use；use:false 必须附 reason。图片按正文顺序自动编号。支持 PNG、JPEG、GIF、WebP；照片/海报建议 PNG 或 JPEG。SVG、HEIC 需先另存为适用格式。

## 环境

构建和打包：Python 3.10+，仅标准库。macOS/Linux 通常用 python3，Windows 可用 py -3。

完整视觉检查：Node.js 18+ 与 Playwright。先检查 Codex 已提供的依赖和浏览器；可用 `--modules` 指向含 Playwright 的 node_modules，`--browser` 指向已安装的 Chromium/Chrome/Edge。未指定时先尝试 Playwright 自带 Chromium，再查常见系统浏览器位置。

没有 Playwright 时，可在单独工具目录安装（不要装进 Skill 包）：

```sh
npm install --prefix ./wechat-tools playwright
```

已有 Chrome/Edge 时用 --browser 指定；没有可用浏览器时再执行 `npx --prefix ./wechat-tools playwright install chromium`。这一步需要联网下载。缺少依赖时明确说明缺口；可先交付 HTML，但不能称视觉检查已通过。

## 三步运行

以下命令在 Skill 根目录运行；将路径换成当期目录。--out 必须是尚不存在的新目录，修改时生成新版本，防止覆盖旧成品。

```sh
python3 scripts/render.py build --article examples/demo/article.md --config examples/demo/issue.json --out ./demo-output
node scripts/check_layout.cjs --dir ./demo-output
python3 scripts/render.py pack --dir ./demo-output
```

指定外部依赖的检查命令示例：

```sh
node scripts/check_layout.cjs --dir ./demo-output --modules ./wechat-tools/node_modules --browser /path/to/browser
```

检查图片加载、比例、段落和标题行数、手机溢出、独立正文、复制正文/标题/摘要及宽屏切换；保存首屏、整篇与逐张配图截图。剪贴板接口若受环境限制，记录“未验证”，不误报通过。图片身份和文案事实仍需对照资料核实。

打包要求结构检查通过；正文、预览或图片修改后须重新检查，打包会拒绝过期报告。超长段落、无法实读系统剪贴板等保留为提示，不能宣称全部验证完成。ZIP 包含交付文件，不含工具依赖。

## 公众号使用

打开“公众号排版预览.html”，复制标题/摘要到对应栏位；复制正文样式后，按编号上传“配图”中的图片并删除提示文字。HTML 预览有图片，不代表复制时已把本地图片传到公众号服务器。最后在公众号后台检查真实手机预览；操作后台和发布另按用户授权执行。

## 安装与更新

GitHub 仓库安装路径为 `skills/ai-action-pi-gongzhonghao`。可让 Codex 根据链接安装。本地 ZIP 解压后，复制整个 ai-action-pi-gongzhonghao 文件夹到 Codex 的 skills 目录（默认 ~/.codex/skills，自定义 CODEX_HOME 时用其下的 skills）。

先检查同名目录。首次安装不改其他配置；已安装则核对版本并保留本地修改，未经更新授权不覆盖。安装后下一轮对话可用 `$ai-action-pi-gongzhonghao` 调用。GitHub 更新不会自动替换已安装版本。
