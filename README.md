# AI行动π · 公众号文章创作与排版

Codex Skill，当前版本为 v1.0.1。供团队成员轮流独立执笔，完成公众号文章的资料整理、写稿、配图、墨绿色排版、检查和本地导出。

支持活动预告、往期回顾和主题文章。每期可以单独设置执笔人、标题分行、活动信息、邀请对象和图片。

## 安装到 Codex

将下面这段话交给自己的 Codex，安装后下一轮对话即可调用。

> 请安装这个 GitHub 目录中的 Skill，并检查排版与本地预览所需的工具。安装地址为 https://github.com/alex584221185-wq/ai-action-pi-gongzhonghao/tree/main/skills/ai-action-pi-gongzhonghao 。如已安装同名版本，请先核对版本并保留本地修改。

也可下载仓库 ZIP，将 `skills/ai-action-pi-gongzhonghao` 整个文件夹放入 Codex 的 skills 目录。默认位置为 `~/.codex/skills`，自定义 CODEX_HOME 时使用其下的 skills。

## 每期使用

将当期资料、参考文稿、照片和海报放进工作文件夹，然后交给 Codex。

> 使用 $ai-action-pi-gongzhonghao。我是本期执笔人，请根据这个文件夹里的资料制作公众号文章。沿用墨绿色风格，先核对活动信息和人物，完成写稿、配图、排版和导出。初稿里标清图片占位、所需画面和图注。重要资料缺失时再问我。

需要分步讨论时，可要求先看提纲或初稿。机器配置由 Codex 整理，作者可直接填写资料模板。[本期资料模板](skills/ai-action-pi-gongzhonghao/assets/本期资料模板.md)

## 交付内容

- 含可见图片占位的阅读初稿，提供 Markdown、HTML 和手机截图。
- 可继续修改的排版源文稿与本期配置。
- 自带图片的图文预览，支持图片占位和配图效果切换。
- 可复制的正文 HTML、标题和摘要。
- 按顺序编号的图片、配图清单、检查报告和 ZIP 排版包。

粘贴正文后，在公众号后台按编号上传图片，再检查真实手机预览。

## 查看示例

随包示例为虚构的 AI 写作练习，配有原创示意图。阅读初稿中的每处占位会说明图片内容、对应文件和图注。[示例初稿](skills/ai-action-pi-gongzhonghao/examples/demo/初稿_图片占位.md)

## 运行环境

构建和打包使用 Python 3.10+ 标准库。完整手机检查使用 Node.js 18+、Playwright，以及可用的 Chromium、Chrome 或 Edge。Codex 可先检查并复用已有运行环境。[环境准备与操作说明](skills/ai-action-pi-gongzhonghao/references/workflow.md)

在 Skill 目录中运行示例。

```sh
python3 scripts/render.py build --article examples/demo/article.md --config examples/demo/issue.json --out ./demo-output
node scripts/check_layout.cjs --dir ./demo-output
python3 scripts/render.py pack --dir ./demo-output
```

若 Playwright 或浏览器位于其他目录，按操作说明为检查命令提供 `--modules` 或 `--browser`。

## 更新

GitHub 更新后，各成员在 Codex 中更新已安装的版本，并保留需要的本地修改。

v1.0.1 加入可见图片占位初稿和预览切换。v1.0.0 为首次打包版本。

## 验证

在仓库根目录运行行为检查。

```sh
python3 -m unittest discover -s tests -v
```

当前版本已在 macOS 检查 360、390、430px 手机布局、图片完整性、复制功能、独立目录安装与导出。Windows 和 Linux 的原生运行、公众号后台操作仍待实测。[验证记录](VALIDATION.md)
