import os
import platform
import re
import uuid
import shutil
import subprocess
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote
from flask import Flask, request, jsonify, send_file, render_template

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / 'uploads'
OUTPUT_DIR = BASE_DIR / 'outputs'
DEV_SERVER_PORT = 5001

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB（图片可能较大）
app.config['UPLOAD_FOLDER'] = str(UPLOAD_DIR)
app.config['OUTPUT_FOLDER'] = str(OUTPUT_DIR)

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

ALLOWED_TO_MD = {
    'pdf', 'docx', 'doc', 'pptx', 'ppt', 'xlsx', 'xls',
    'html', 'htm', 'csv', 'json', 'xml', 'zip', 'epub',
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'wav', 'mp3'
}

IMAGE_EXTS = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'tiff', 'tif'}

PDF_CSS = """
body { max-width: 780px; margin: 2rem auto; padding: 0 1.2rem;
       font-family: 'Noto Sans CJK SC', 'PingFang SC', 'Microsoft YaHei',
                    -apple-system, BlinkMacSystemFont, sans-serif;
       font-size: 15px; line-height: 1.75; color: #24292e; }
h1,h2,h3,h4,h5,h6 { margin-top: 1.4em; margin-bottom: .45em; font-weight: 600; line-height: 1.3; }
h1 { font-size: 1.9em; border-bottom: 2px solid #eaecef; padding-bottom: .25em; }
h2 { font-size: 1.45em; border-bottom: 1px solid #eaecef; padding-bottom: .2em; }
a  { color: #0366d6; }
code { background: #f6f8fa; padding: .15em .35em; border-radius: 3px;
       font-family: 'SFMono-Regular', Consolas, monospace; font-size: .88em; }
pre  { background: #f6f8fa; padding: .9em 1.1em; border-radius: 5px; overflow-x: auto; }
pre code { background: none; padding: 0; }
blockquote { border-left: 4px solid #dfe2e5; margin: 0; padding: .4em .9em; color: #6a737d; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; }
th,td { border: 1px solid #dfe2e5; padding: .45em .75em; }
th    { background: #f6f8fa; font-weight: 600; }
tr:nth-child(even) td { background: #fafbfc; }
img { max-width: 100%; }
hr  { border: none; border-top: 1px solid #eaecef; margin: 1.8em 0; }
"""

def configured_dir(config_key, default_dir):
    path = Path(app.config.get(config_key, default_dir))
    if not path.is_absolute():
        path = BASE_DIR / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_name(filename):
    """保留中文文件名，同时清理路径分隔符和 Windows 非法字符。"""
    raw = str(filename or '').replace('\\', '/')
    name = raw.rsplit('/', 1)[-1].strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    name = name.strip().strip('.')
    return name or 'file'


def normalize_image_ref(path):
    """把 Markdown/HTML 图片引用规整成可匹配的本地路径字符串。"""
    ref = unquote(str(path or '').strip())
    if ref.startswith('<') and ref.endswith('>'):
        ref = ref[1:-1].strip()
    ref = ref.replace('\\', '/')
    ref = ref.split('#', 1)[0].split('?', 1)[0]
    return ref


def image_basename(path):
    return Path(normalize_image_ref(path)).name


def find_uploaded_image(path, image_map):
    basename = image_basename(path)
    if basename in image_map:
        return image_map[basename]

    normalized = normalize_image_ref(path)
    for orig, saved in image_map.items():
        if normalized.endswith(orig):
            return saved
    return None


def send_generated_file(path, download_name, mimetype):
    data = Path(path).read_bytes()
    return send_file(
        BytesIO(data),
        as_attachment=True,
        download_name=download_name,
        mimetype=mimetype,
    )


def run_text(cmd, timeout=120, **kwargs):
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=timeout,
        **kwargs,
    )


def inject_css_once(html_path, css):
    html = Path(html_path).read_text(encoding='utf-8')
    if '</head>' in html:
        html = html.replace('</head>', f'<style>\n{css}\n</style>\n</head>', 1)
    else:
        html = f'<style>\n{css}\n</style>\n' + html
    Path(html_path).write_text(html, encoding='utf-8')


def render_pdf_with_weasyprint(html_path, out_path):
    try:
        from weasyprint import HTML
        HTML(filename=str(html_path), base_url=str(Path(html_path).parent)).write_pdf(str(out_path))
        return Path(out_path).exists(), ''
    except Exception as exc:
        return False, str(exc)


def cjk_font_candidates():
    env_font = os.environ.get('PDF_CJK_FONT', '').strip()
    system = platform.system().lower()
    if system == 'windows':
        defaults = ['Microsoft YaHei', 'SimSun']
    elif system == 'darwin':
        defaults = ['PingFang SC', 'Songti SC']
    else:
        defaults = ['Noto Serif CJK SC', 'Noto Sans CJK SC', 'WenQuanYi Zen Hei']

    candidates = []
    for font in [env_font, *defaults]:
        if font and font not in candidates:
            candidates.append(font)
    return candidates


def render_pdf_with_xelatex(md_path, out_path, work_dir):
    errors = []
    for font in cjk_font_candidates():
        out_path.unlink(missing_ok=True)
        result = run_text(
            ['pandoc', md_path.name, '-o', str(out_path),
             '--pdf-engine=xelatex', '--standalone',
             '--resource-path=.',
             '-V', f'CJKmainfont={font}',
             '-V', 'geometry:margin=2cm'],
            timeout=120,
            cwd=str(work_dir),
        )
        if result.returncode == 0 and out_path.exists():
            return True, ''
        message = result.stderr.strip() or result.stdout.strip() or f'pandoc exited with {result.returncode}'
        errors.append(f'{font}: {message}')
    return False, '\n'.join(errors)


def find_chrome():
    program_files = [
        os.environ.get('PROGRAMFILES'),
        os.environ.get('PROGRAMFILES(X86)'),
        os.environ.get('LOCALAPPDATA'),
    ]
    path_candidates = [
        Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
        Path('/Applications/Chromium.app/Contents/MacOS/Chromium'),
        Path('/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary'),
    ]
    for base in program_files:
        if base:
            path_candidates.extend([
                Path(base) / 'Google/Chrome/Application/chrome.exe',
                Path(base) / 'Chromium/Application/chrome.exe',
            ])

    for candidate in path_candidates:
        if candidate.is_file():
            return str(candidate)

    for command in (
        'google-chrome',
        'google-chrome-stable',
        'chromium',
        'chromium-browser',
        'chrome',
        'chrome.exe',
    ):
        found = shutil.which(command)
        if found:
            return found
    return None


def command_available(command):
    try:
        result = subprocess.run([command, '--version'], capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False


def rewrite_image_paths(md_text, image_map):
    """
    将 Markdown 中的图片路径（相对或绝对）重写为临时目录中的文件名。
    image_map: { 原始文件名（不含目录）: 保存到临时目录的文件名 }

    处理两种语法：
      ![alt](path)
      <img src="path" ...>
    """
    def replace_md(m):
        alt, path = m.group(1), m.group(2)
        saved = find_uploaded_image(path, image_map)
        if saved:
            return f'![{alt}]({saved})'
        return m.group(0)

    def replace_html(m):
        prefix, path, suffix = m.group(1), m.group(2), m.group(3)
        saved = find_uploaded_image(path, image_map)
        if saved:
            return f'{prefix}{saved}{suffix}'
        return m.group(0)

    md_text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replace_md, md_text)
    md_text = re.sub(r'(<img\s[^>]*src=["\'])([^"\']+)(["\'][^>]*>)',
                     replace_html, md_text, flags=re.IGNORECASE)
    return md_text


def setup_workdir(request_files):
    """
    创建临时工作目录，保存 .md 文件和所有图片，返回：
      (work_dir, md_path, filename, image_map, error_str)
    """
    md_file = request_files.get('mdfile')
    if not md_file or md_file.filename == '':
        return None, None, None, None, '请上传 Markdown 文件'

    work_dir = configured_dir('UPLOAD_FOLDER', UPLOAD_DIR) / uuid.uuid4().hex
    work_dir.mkdir(parents=True, exist_ok=True)

    # 保存 .md
    md_name = safe_name(md_file.filename)
    md_path = work_dir / md_name
    md_file.save(md_path)
    md_text = md_path.read_text(encoding='utf-8', errors='replace')

    # 保存图片，建立 原始文件名→保存文件名 的映射
    image_map = {}
    for img_file in request_files.getlist('images'):
        if img_file and img_file.filename:
            orig = safe_name(img_file.filename)
            ext = orig.rsplit('.', 1)[-1].lower() if '.' in orig else ''
            if ext not in IMAGE_EXTS:
                continue
            # 若文件名冲突加前缀
            saved_name = orig
            if (work_dir / saved_name).exists():
                saved_name = f'{uuid.uuid4().hex[:6]}_{orig}'
            save_path = work_dir / saved_name
            img_file.save(save_path)
            image_map[orig] = saved_name

    # 重写路径并更新 .md
    if image_map:
        md_text = rewrite_image_paths(md_text, image_map)
        md_path.write_text(md_text, encoding='utf-8')

    # 文件名（去扩展名）
    base_name = Path(md_name).stem
    filename = ''.join(c for c in base_name if c.isalnum() or c in '-_ ')[:50] or 'document'

    return work_dir, md_path, filename, image_map, None


# ── 路由 ──────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/to-markdown', methods=['POST'])
def to_markdown():
    """任意格式 → Markdown（markitdown，不涉及图片上传）"""
    if 'file' not in request.files:
        return jsonify({'error': '请选择文件'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_TO_MD:
        return jsonify({'error': f'不支持的文件格式：.{ext}'}), 400

    upload_dir = configured_dir('UPLOAD_FOLDER', UPLOAD_DIR)
    original_name = safe_name(file.filename)
    input_path = upload_dir / f'{uuid.uuid4().hex}_{original_name}'
    file.save(input_path)

    try:
        result = run_text(['markitdown', str(input_path)], timeout=60)
        if result.returncode != 0:
            return jsonify({'error': result.stderr.strip() or '转换失败'}), 500
        return jsonify({'success': True, 'markdown': result.stdout,
                        'original_name': original_name})
    except subprocess.TimeoutExpired:
        return jsonify({'error': '转换超时'}), 500
    except FileNotFoundError:
        return jsonify({'error': 'markitdown 未安装，请运行: pip install markitdown[all]'}), 500
    finally:
        input_path.unlink(missing_ok=True)


@app.route('/api/to-docx', methods=['POST'])
def to_docx():
    """Markdown + 图片 → Word (.docx)"""
    work_dir, md_path, filename, _, err = setup_workdir(request.files)
    if err:
        return jsonify({'error': err}), 400

    out_path = configured_dir('OUTPUT_FOLDER', OUTPUT_DIR) / f'{uuid.uuid4().hex}.docx'
    try:
        r = run_text(
            ['pandoc', md_path.name, '-o', str(out_path), '--standalone',
             '--resource-path=.'],
            timeout=60,
            cwd=str(work_dir),
        )
        if r.returncode != 0:
            return jsonify({'error': r.stderr.strip() or '转换失败'}), 500
        return send_generated_file(
            out_path,
            download_name=f'{filename}.docx',
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )
    except FileNotFoundError:
        return jsonify({'error': 'pandoc 未安装'}), 500
    except subprocess.TimeoutExpired:
        return jsonify({'error': '转换超时'}), 500
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        out_path.unlink(missing_ok=True)


@app.route('/api/to-pdf', methods=['POST'])
def to_pdf():
    """Markdown + 图片 → PDF（Pandoc + XeLaTeX 优先，自动回退其他引擎）"""
    work_dir, md_path, filename, _, err = setup_workdir(request.files)
    if err:
        return jsonify({'error': err}), 400

    uid = uuid.uuid4().hex
    html_path = work_dir / f'{uid}.html'
    out_path = configured_dir('OUTPUT_FOLDER', OUTPUT_DIR) / f'{uid}.pdf'

    try:
        def build_embedded_html():
            result = run_text(
                ['pandoc', md_path.name, '-o', str(html_path), '--standalone',
                 '--embed-resources',
                 '--highlight-style=pygments',
                 '--resource-path=.',
                 f'--metadata=title:{filename}'],
                timeout=30,
                cwd=str(work_dir),
            )
            if result.returncode != 0 or not html_path.exists():
                return False, result.stderr.strip() or 'Pandoc 生成 HTML 失败'
            inject_css_once(html_path, PDF_CSS)
            return True, ''

        # 方案 1：Pandoc + XeLaTeX（中文和数学公式效果最好）
        if command_available('xelatex'):
            ok, _ = render_pdf_with_xelatex(md_path, out_path, work_dir)
            if ok and out_path.exists():
                return send_generated_file(
                    out_path,
                    download_name=f'{filename}.pdf',
                    mimetype='application/pdf',
                )

        # 方案 2：Chrome headless（HTML 打印 PDF，适合普通图文 Markdown）
        chrome_bin = find_chrome()
        html_ready, html_error = build_embedded_html()
        if html_ready and chrome_bin:
            chrome_profile = work_dir / 'chrome-profile'
            chrome_profile.mkdir(exist_ok=True)
            r2 = run_text(
                [chrome_bin,
                 '--headless=new',
                 '--disable-gpu',
                 '--no-sandbox',
                 '--disable-dev-shm-usage',
                 '--no-first-run',
                 '--no-default-browser-check',
                 '--disable-background-networking',
                 f'--user-data-dir={chrome_profile}',
                 f'--print-to-pdf={out_path}',
                 '--print-to-pdf-no-header',
                 html_path.resolve().as_uri()],
                timeout=60,
            )
            if r2.returncode == 0 and out_path.exists():
                return send_generated_file(
                    out_path,
                    download_name=f'{filename}.pdf',
                    mimetype='application/pdf',
                )

        # 方案 3：WeasyPrint（Python 后备，避免浏览器进程限制）
        if html_ready:
            ok, _ = render_pdf_with_weasyprint(html_path, out_path)
            if ok and out_path.exists():
                return send_generated_file(
                    out_path,
                    download_name=f'{filename}.pdf',
                    mimetype='application/pdf',
                )

        # 方案 4：wkhtmltopdf（老 WebKit 引擎，仅作为兜底）
        if html_ready and command_available('wkhtmltopdf'):
            r2 = run_text(
                ['wkhtmltopdf', '--encoding', 'utf-8',
                 '--enable-local-file-access',
                 '--margin-top', '15mm', '--margin-bottom', '15mm',
                 '--margin-left', '15mm', '--margin-right', '15mm',
                 str(html_path), str(out_path)],
                timeout=90,
            )
            if r2.returncode == 0 and out_path.exists():
                return send_generated_file(
                    out_path,
                    download_name=f'{filename}.pdf',
                    mimetype='application/pdf',
                )

        # 方案 5：md-to-pdf（需先: PUPPETEER_SKIP_DOWNLOAD=1 npm install -g md-to-pdf）
        if command_available('md-to-pdf'):
            chrome_path = chrome_bin or ''
            cmd = ['md-to-pdf', md_path.name, '--dest', str(out_path)]
            env = os.environ.copy()
            if chrome_path:
                env['PUPPETEER_EXECUTABLE_PATH'] = chrome_path
            r = run_text(cmd, timeout=60, cwd=str(work_dir), env=env)
            if r.returncode == 0 and out_path.exists():
                return send_generated_file(
                    out_path,
                    download_name=f'{filename}.pdf',
                    mimetype='application/pdf',
                )

        # 方案 6：Pandoc 默认 PDF 引擎兜底
        r = run_text(
            ['pandoc', md_path.name, '-o', str(out_path), '--standalone',
             '--resource-path=.'],
            timeout=120,
            cwd=str(work_dir),
        )
        if r.returncode == 0 and out_path.exists():
            return send_generated_file(
                out_path,
                download_name=f'{filename}.pdf',
                mimetype='application/pdf',
            )

        return jsonify({'error':
            'PDF 转换失败。\n'
            '推荐安装 Pandoc + XeLaTeX，并确保系统有可用中文字体。\n'
            '也可以安装 WeasyPrint 或 Google Chrome 作为后备。'}), 500
    except FileNotFoundError:
        return jsonify({'error': 'pandoc 未安装'}), 500
    except subprocess.TimeoutExpired:
        return jsonify({'error': '转换超时'}), 500
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        out_path.unlink(missing_ok=True)


@app.route('/api/check-deps', methods=['GET'])
def check_deps():
    """直接调用各工具的 --version 检测，跨平台兼容（不依赖 which/where）"""
    probes = {
        'markitdown': 'markitdown',
        'pandoc': 'pandoc',
        'xelatex': 'xelatex',
        'wkhtmltopdf': 'wkhtmltopdf',
        'md-to-pdf': 'md-to-pdf',
    }
    deps = {name: command_available(command) for name, command in probes.items()}
    deps['chrome'] = bool(find_chrome())
    return jsonify(deps)


def run_server():
    app.run(debug=True, port=DEV_SERVER_PORT)


if __name__ == '__main__':
    run_server()
