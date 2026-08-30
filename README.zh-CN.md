# cool cool latex editor

[English](README.md) | [简体中文](README.zh-CN.md)

一个轻量、本地、Git-native 的 LaTeX 文章编辑与评阅界面。LaTeX 始终是唯一源文件；浏览器只提供更适合阅读、微调、评论和高亮的中间视图。

## 它能做什么

- 把 LaTeX 渲染成居中的文章视图，而不是 IDE 或 PDF 阅读器。
- 递归读取静态 `\\input{...}` 和 `\\include{...}`，包括被引用文件继续引用的更深层文件。
- 在文章视图中保留论文标题，并明确显示 “Abstract” 标题。
- 把 BibTeX citation 显示为作者–年份标签，悬停可查看完整条目。进入段落编辑后，点击引用即可修改 cite 命令、options、keys，以及对应 BibTeX 条目的 author、year 和 title。
- 点击段落即可小范围修改，同时保护公式、强调、链接等 LaTeX 结构。
- 选中文字可以添加段落评论、全文评论和仅供编辑使用的高亮。
- 评论与高亮以 TeX comment 保存，因此不会进入正常的 LaTeX 或 PDF 输出。
- 支持 Reading、Bubbles 两种显示模式，以及文档 outline；Source 会打开当前段落真正所属的文件，并准确跳到对应行。
- 自动发现磁盘上的外部更新，不会擅自覆盖浏览器中尚未保存的编辑。
- 每条标注都保留用户选择的名字，适合通过 Git 传递多人评阅历史。

这个包没有运行时依赖，默认只监听 `127.0.0.1`。

## 安装

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

## 打开文章

把 `.tex` 文件作为第一个参数：

```bash
cool-cool-latex-editor draft/proposal.tex --open
```

默认地址是 <http://127.0.0.1:4179>。可以指定端口，或者用端口 `0` 让操作系统自动选择空闲端口：

```bash
cool-cool-latex-editor draft/proposal.tex --port 52732 --open
cool-cool-latex-editor draft/proposal.tex --port 0 --open
```

编辑器会自动寻找 `.tex` 文件所在的 Git 仓库。只有自动发现不合适时才需要使用 `--root /path/to/repository`。

多文件文章应传入主入口文件。页面顶部会显示已经载入的源文件数量；悬停可以查看文件路径和未解析引用警告。文章视图中的编辑、评论和高亮会写回所选段落真正所在的引用文件。**Source** 会跟随当前段落打开它所属的文件和行号，也可从下拉菜单切换所有已载入的 TeX 文件。`\\bibliography{...}` 或 `\\addbibresource{...}` 指向的 BibTeX 文件会作为显示依赖被监测；引用编辑会写回条目所在的真实 `.bib` 文件，同时保留其他字段与条目。

查看当前安装版本：

```bash
cool-cool-latex-editor --version
```

## 更新

通过 `pipx` 安装时：

```bash
pipx upgrade cool-cool-latex-editor
```

通过普通 `pip` 安装时：

```bash
python3 -m pip install --upgrade "git+https://github.com/zmk5566/coool-cool-latex-editor.git"
```

升级后请重启正在运行的编辑器进程。应用不会在后台静默更新自身。

## 在 Codex CLI 中使用

仓库自带一个 Codex skill。它会告诉 Codex 如何定位文章、启动编辑器、解释评阅模式、检查版本，以及在你明确要求时执行更新。

1. 在终端运行 `codex`，进入 Codex CLI。
2. 把下面这句话输入 **Codex 的对话提示符**。它不是 shell 命令：

   ```text
   $skill-installer install https://github.com/zmk5566/coool-cool-latex-editor/tree/main/skills/cool-cool-latex-editor
   ```

3. Codex 通常会自动发现新 skill；如果 `$cool-cool-latex-editor` 没有出现，请退出并重新启动 Codex CLI。

安装后可以直接说：

```text
用 cool cool latex editor 打开 draft/proposal.tex，端口用 52732。
```

也可以显式调用：

```text
Use $cool-cool-latex-editor to open draft/proposal.tex.
```

安装和更新软件会改变本机环境，因此 Codex 在执行相应命令前仍可能请求授权。

### 手动安装 skill

Codex CLI 也会从个人目录 `$HOME/.agents/skills` 读取 skill。如果已经 clone 了这个仓库，可以建立一个符号链接：

```bash
mkdir -p "$HOME/.agents/skills"
ln -s "/absolute/path/to/coool-cool-latex-editor/skills/cool-cool-latex-editor" \
  "$HOME/.agents/skills/cool-cool-latex-editor"
```

这种方式下，更新仓库也会同步更新 skill：

```bash
git -C /absolute/path/to/coool-cool-latex-editor pull --ff-only
```

Codex 通常会自动检测 skill 文件变化；如果没有生效，请重启 Codex CLI。

## Git 工作流

1. `git pull` 后在本地启动编辑器。
2. 编辑正文，添加段落评论、overall comment 或高亮。
3. 需要 LaTeX 结构修改时切换到 **Source**；它会从当前段落对应的真实源文件位置开始。
4. 检查正常的 Git diff，然后 commit 和 push `.tex` 的修改。

评论状态只有 `open` 和 `addressed`；“已处理”不暗示修改一定由 AI 完成。编辑器元数据都是合法 TeX comments，正常 LaTeX/PDF 输出不会显示。Source 模式还可以导出移除这些元数据的 clean `.tex`。

## 安全边界

- 服务默认只监听 `127.0.0.1`，并且没有身份验证；不要直接暴露到公网。
- 中间渲染器只处理标题、章节、段落和列表等写作结构；完整 LaTeX 始终可以在 **Source** 中编辑。
- 静态 `\\input` 和 `\\include` 路径必须解析到当前 Git 仓库内部。由宏动态生成的路径不会被猜测，而会显示为 warning。
- 如果外部程序更新了源文件，页面只会提示 reload，不会自动丢弃未保存内容。

## 开发

```bash
python3 -m unittest discover -s tests -v
node --check cool_cool_latex_editor/static/app.js
```

当前版本：`0.3.0`
