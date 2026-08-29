# cool cool latex editor

一个轻量、本地、Git-native 的 LaTeX 文章编辑与评阅界面。LaTeX 始终是唯一源文件；浏览器只提供更适合阅读、微调、评论和高亮的中间视图。

A lightweight local review surface for Git-managed LaTeX manuscripts. LaTeX remains the single source of truth.

## 它做什么 / What it does

- 把 LaTeX 渲染成居中的文章视图，而不是 IDE 或 PDF 阅读器。
- 点击段落即可小范围修改；LaTeX 公式、强调、链接等结构会受到保护。
- 选中文字可以添加评论、高亮或编辑；另有 overall comment。
- 评论与高亮以 TeX comment 保存，因此不会进入正常的 PDF 输出。
- 支持阅读模式、类似 Google Docs 的气泡模式、文档 outline 和完整 Source 模式。
- 自动发现磁盘上的外部更新；有未保存内容时不会擅自覆盖。
- 评论作者名随 `.tex` 文件进入 Git，适合多人各自在本地评阅。

The package has no runtime dependencies and binds to `127.0.0.1` by default.

## 安装 / Install

推荐使用 `pipx`：

```bash
pipx install "git+https://github.com/zmk5566/coool-cool-latex-editor.git"
```

也可以安装到当前 Python 环境：

```bash
python3 -m pip install "git+https://github.com/zmk5566/coool-cool-latex-editor.git"
```

本地开发安装：

```bash
git clone https://github.com/zmk5566/coool-cool-latex-editor.git
cd coool-cool-latex-editor
python3 -m pip install -e .
```

## 打开文章 / Open a manuscript

```bash
cool-cool-latex-editor draft/proposal.tex --open
```

默认地址是 <http://127.0.0.1:4179>。可以指定端口，或用端口 `0` 自动选择空闲端口：

```bash
cool-cool-latex-editor draft/proposal.tex --port 52732 --open
cool-cool-latex-editor draft/proposal.tex --port 0 --open
```

编辑器会从 `.tex` 文件所在位置自动寻找 Git 仓库根目录。只有自动发现不合适时才需要 `--root /path/to/repository`。

查看当前安装版本：

```bash
cool-cool-latex-editor --version
```

## 更新 / Update

通过 `pipx` 安装时：

```bash
pipx upgrade cool-cool-latex-editor
```

通过普通 `pip` 安装时：

```bash
python3 -m pip install --upgrade "git+https://github.com/zmk5566/coool-cool-latex-editor.git"
```

升级后重启正在运行的编辑器进程。应用不会在后台自动更新自身。

## 在 Codex 中使用 / Use with Codex

仓库自带一个 Codex skill。可以让 Codex 用 `$skill-installer` 从 GitHub 安装：

```text
$skill-installer install https://github.com/zmk5566/coool-cool-latex-editor/tree/main/skills/cool-cool-latex-editor
```

重启 Codex 后，可以直接说：

```text
用 cool cool latex editor 打开 draft/proposal.tex，端口用 52732。
```

也可以显式调用：

```text
Use $cool-cool-latex-editor to open draft/proposal.tex.
```

这个 skill 会告诉 Codex 如何定位 `.tex`、启动本地服务、检查版本，以及在你明确要求时执行对应的升级命令。安装和升级会改变本机环境，因此 Codex 仍会在需要时请求授权。

## Git 工作流 / Git workflow

1. `git pull` 后在本地启动编辑器。
2. 编辑正文、添加 passage comment、overall comment 或 highlight。
3. 需要 LaTeX 结构修改时切换到 **Source**。
4. 检查正常的 Git diff，然后 commit 和 push。

评论状态只有 `open` 和 `addressed`；“已处理”不暗示修改一定由 AI 完成。编辑器元数据都是合法 TeX comments，正常 LaTeX/PDF 输出不会显示。Source 模式还可以导出移除这些元数据的 clean `.tex`。

## 安全边界 / Safety

- 默认只监听本机 `127.0.0.1`，没有身份验证；不要直接暴露到公网。
- 中间渲染器只处理标题、章节、段落和列表等写作结构；完整 LaTeX 始终可以在 **Source** 中编辑。
- 如果外部程序更新了源文件，页面只会提示 reload，不会自动丢弃未保存内容。

## 开发 / Development

```bash
python3 -m unittest discover -s tests -v
node --check cool_cool_latex_editor/static/app.js
```

当前版本：`0.1.1`
