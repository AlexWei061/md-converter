# MD Converter

文档双向转换工具，基于 **MarkItDown**（微软）+ **Pandoc** 构建，提供简洁的网页界面。

## 功能

| 转换方向 | 支持格式 | 主要依赖 |
|----------|---------|------|
| 其他格式 → Markdown | PDF · DOCX · PPTX · XLSX · HTML · CSV · JSON · XML · ZIP · EPUB · 图片 · 音频 | MarkItDown |
| Markdown → Word | .docx，支持本地图片 | Pandoc |
| Markdown → PDF | .pdf，支持本地图片 | Pandoc + XeLaTeX（推荐）/ Chrome / WeasyPrint / wkhtmltopdf |

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

安装 MiKTeX 后，建议在 MiKTeX Console 中开启 “Install missing packages on-the-fly”。

**Ubuntu**
```bash
sudo apt update
sudo apt install -y pandoc texlive-xetex texlive-lang-chinese texlive-latex-extra fonts-noto-cjk
```

**可选 PDF 后备工具**
```bash
# macOS
brew install --cask google-chrome
brew install wkhtmltopdf

# Ubuntu
sudo apt install -y chromium-browser wkhtmltopdf
```

---

### 第二步：安装 Python 依赖

建议使用虚拟环境：

```bash
cd md-converter

# 创建虚拟环境
python -m venv .venv

# 激活（macOS/Linux）
source .venv/bin/activate

# 激活（Windows）
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

> PDF 转换会按顺序尝试 Pandoc + XeLaTeX、Chrome headless、WeasyPrint、wkhtmltopdf、md-to-pdf、Pandoc 默认 PDF 引擎。中文数学文档推荐安装 XeLaTeX 和中文字体；wkhtmltopdf 只作为兜底，不推荐用于中文公式较多的文档。可通过环境变量 `PDF_CJK_FONT` 指定中文字体。

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
<img src="images/chart.png" alt="chart">
```

上传时选择 `.md` 文件，再把 `demo.png`、`test pic.png`、`chart.png` 一起加入图片列表。后端会按图片文件名匹配并重写临时路径。

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
├── uploads/            # 临时上传目录（自动创建）
└── outputs/            # 临时输出目录（自动创建）
```

---

## 常见问题

**Q: Markdown 里有本地图片，为什么只上传 `.md` 不行？**
A: Markdown 里保存的是图片路径，不是图片内容。请在右侧图片上传区把被引用的图片也一起上传。

**Q: 转换 PDF 时提示缺少 PDF 引擎？**
A: 推荐安装 Pandoc + XeLaTeX。Windows 安装 Pandoc 和 MiKTeX，macOS 安装 Pandoc 和 MacTeX，Ubuntu 安装 `pandoc texlive-xetex texlive-lang-chinese texlive-latex-extra fonts-noto-cjk`。如果暂时不安装 LaTeX，项目会继续回退到 Chrome、WeasyPrint、wkhtmltopdf 等后备引擎。

**Q: 图片/音频文件转换效果不佳？**
A: 图片 OCR 和音频转录需要配置 LLM（如 OpenAI），可在 `app.py` 中扩展 `to_markdown` 路由添加 `llm_client` 参数。

**Q: 上传文件大小限制？**
A: 默认 200MB，可在 `app.py` 中修改 `MAX_CONTENT_LENGTH`。
