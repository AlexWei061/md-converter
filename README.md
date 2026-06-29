# MD Converter

本地运行的文档转换 Web 工具，基于 **Flask + MarkItDown + Pandoc** 构建，提供简洁的网页界面。

当前项目主要支持：

- 其他文件格式转换为 Markdown
- Markdown 转换为 Word
- Markdown 转换为 PDF
- Markdown 转 Word/PDF 时同时上传本地图片

> 当前项目已经移除了 Markdown 转 HTML 下载/预览功能。

## 功能

| 转换方向 | 支持格式 | 主要依赖 |
|----------|---------|------|
| 其他格式 → Markdown | PDF · DOCX · PPTX · XLSX · HTML · CSV · JSON · XML · ZIP · EPUB · 图片 · 音频 | MarkItDown |
| Markdown → Word | .docx，支持本地图片 | Pandoc |
| Markdown → PDF | .pdf，支持本地图片 | Pandoc + XeLaTeX（推荐）/ Chrome / WeasyPrint / wkhtmltopdf |

---

## PDF 引擎优先级

Markdown 转 PDF 时，后端会按下面顺序尝试：

1. Pandoc + XeLaTeX
2. Chrome headless
3. WeasyPrint
4. wkhtmltopdf
5. md-to-pdf
6. Pandoc 默认 PDF 引擎

中文和数学公式较多的 Markdown，推荐安装 **Pandoc + XeLaTeX + 中文字体**。`wkhtmltopdf` 只作为兜底方案，它对中文字体和 LaTeX 公式支持较弱。

XeLaTeX 中文字体会自动按平台尝试：

- Windows：`Microsoft YaHei`、`SimSun`
- macOS：`PingFang SC`、`Songti SC`
- Linux/Ubuntu：`Noto Serif CJK SC`、`Noto Sans CJK SC`、`WenQuanYi Zen Hei`

也可以通过环境变量指定字体：

```bash
PDF_CJK_FONT="Noto Serif CJK SC" python app.py
```

Windows PowerShell：

```powershell
$env:PDF_CJK_FONT="Microsoft YaHei"
python app.py
```

---

## 快速开始

### 第一步：安装系统依赖

**macOS**
```bash
brew install pandoc
brew install --cask mactex
```

**Windows**
```powershell
winget install JohnMacFarlane.Pandoc
winget install MiKTeX.MiKTeX
```

安装 MiKTeX 后，建议打开 MiKTeX Console，将 “Install missing packages on-the-fly” 设置为 `Yes`。

**Ubuntu**
```bash
sudo apt update
sudo apt install -y pandoc texlive-xetex texlive-lang-chinese texlive-latex-extra fonts-noto-cjk
```

**可选 PDF 后备工具**
```powershell
# Windows
winget install Google.Chrome
```

```bash
# macOS
brew install --cask google-chrome
brew install wkhtmltopdf

# Ubuntu/Debian
sudo apt install -y chromium-browser wkhtmltopdf
```

---

### 第二步：安装 Python 依赖

建议使用虚拟环境：

```bash
cd md-converter
python -m venv .venv
```

macOS/Linux：

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> `requirements.txt` 只安装 Python 依赖。Pandoc、XeLaTeX、Chrome、wkhtmltopdf、md-to-pdf 都是外部命令，需要按系统单独安装。

---

### 第三步：启动服务

```bash
python app.py
```

浏览器访问 **http://localhost:5000** 即可使用。

---

## 界面说明

### 左侧面板：文件 → Markdown
1. 拖拽文件或点击选择（支持 PDF/Word/PPT/Excel/HTML 等）
2. 点击「转换为 Markdown」
3. 结果显示在下方文本框
4. 可复制、下载 `.md` 文件，或点击「发送到右侧」继续处理

### 右侧面板：Markdown → 文件
1. 粘贴或编辑 Markdown 内容，也可以上传 `.md` 文件
2. 如果 Markdown 里引用了本地图片，同时在图片上传区选择这些图片
3. 填写输出文件名（可选）
4. 点击「下载 Word」或「下载 PDF」

带图片 Markdown 示例：

```markdown
![截图](images/demo.png)
![带空格的图片](<images/test pic.png>)
![Windows 路径](images\chart.png)
<img src="images/chart.png" alt="chart">
```

上传时选择 `.md` 文件，再把 `demo.png`、`test pic.png`、`chart.png` 一起加入图片列表。后端会按图片文件名匹配并重写临时路径。

支持的图片路径形式包括：

- `![](img/a.png)`
- `![](<img/a b.png>)`
- URL 编码空格，如 `test%20pic.png`
- Windows 反斜杠路径，如 `images\图 1.png`
- HTML 图片标签，如 `<img src="images/a.png">`

如果不同目录下存在同名图片，目前仍按文件名匹配，建议避免同名图片。

---

## 依赖状态

页面顶部状态栏会实时显示各依赖是否已安装：
- 🟢 绿色：已安装，可正常使用
- 🔴 红色：未安装，对应功能不可用

当前检测项包括 `markitdown`、`pandoc`、`xelatex`、`wkhtmltopdf`、`Chrome`、`md-to-pdf`。

---

## 项目结构

```
md-converter/
├── app.py              # Flask 后端
├── requirements.txt    # Python 依赖
├── README.md
├── templates/
│   └── index.html      # 前端页面
├── tests/
│   └── test_app_paths.py
├── uploads/            # 临时上传目录（自动创建）
└── outputs/            # 临时输出目录（自动创建）
```

---

## 接口概览

| 接口 | 方法 | 用途 |
|------|------|------|
| `/` | GET | Web 页面 |
| `/api/check-deps` | GET | 检测本地依赖状态 |
| `/api/to-markdown` | POST | 文件转 Markdown |
| `/api/to-docx` | POST | Markdown 转 Word |
| `/api/to-pdf` | POST | Markdown 转 PDF |

`/api/to-docx` 和 `/api/to-pdf` 使用 `multipart/form-data`：

- `mdfile`：Markdown 文件
- `images`：可选，可上传多张本地图片

---

## 常见问题

**Q: Markdown 里有本地图片，为什么只上传 `.md` 不行？**
A: Markdown 里保存的是图片路径，不是图片内容。请在右侧图片上传区把被引用的图片也一起上传。

**Q: 转换 PDF 时提示缺少 PDF 引擎？**
A: 推荐安装 Pandoc + XeLaTeX。Windows 安装 Pandoc 和 MiKTeX，macOS 安装 Pandoc 和 MacTeX，Ubuntu 安装 `pandoc texlive-xetex texlive-lang-chinese texlive-latex-extra fonts-noto-cjk`。如果暂时不安装 LaTeX，项目会继续回退到 Chrome、WeasyPrint、wkhtmltopdf 等后备引擎。

**Q: PDF 里中文缺失或公式显示成源码怎么办？**
A: 优先确认 `xelatex` 可用，并安装中文字体。Ubuntu 推荐安装 `fonts-noto-cjk`，Windows 可使用 `Microsoft YaHei`，macOS 可使用 `PingFang SC`。也可以用 `PDF_CJK_FONT` 指定字体。

**Q: 为什么 wkhtmltopdf 只是兜底？**
A: `wkhtmltopdf` 使用较老的 WebKit 渲染能力，对现代 CSS、中文字体和 LaTeX 公式支持有限。中文数学文档建议走 Pandoc + XeLaTeX。

**Q: MarkItDown 显示红色怎么办？**
A: 先确认当前 Python 环境已经运行 `pip install -r requirements.txt`，然后执行 `markitdown --version` 检查命令是否可用。

**Q: 图片/音频文件转换效果不佳？**
A: 图片 OCR 和音频转录需要配置 LLM（如 OpenAI），可在 `app.py` 中扩展 `to_markdown` 路由添加 `llm_client` 参数。

**Q: 上传文件大小限制？**
A: 默认 200MB，可在 `app.py` 中修改 `MAX_CONTENT_LENGTH`。
