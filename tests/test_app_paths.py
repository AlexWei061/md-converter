import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import app as app_module


class ConverterPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.upload_dir = self.tmp_path / "uploads"
        self.output_dir = self.tmp_path / "outputs"
        self.upload_dir.mkdir()
        self.output_dir.mkdir()

        self.old_upload = app_module.app.config.get("UPLOAD_FOLDER")
        self.old_output = app_module.app.config.get("OUTPUT_FOLDER")
        app_module.app.config["UPLOAD_FOLDER"] = str(self.upload_dir)
        app_module.app.config["OUTPUT_FOLDER"] = str(self.output_dir)

        self.old_upload_dir = getattr(app_module, "UPLOAD_DIR", None)
        self.old_output_dir = getattr(app_module, "OUTPUT_DIR", None)
        if hasattr(app_module, "UPLOAD_DIR"):
            app_module.UPLOAD_DIR = self.upload_dir
        if hasattr(app_module, "OUTPUT_DIR"):
            app_module.OUTPUT_DIR = self.output_dir

        self.client = app_module.app.test_client()

    def tearDown(self):
        app_module.app.config["UPLOAD_FOLDER"] = self.old_upload
        app_module.app.config["OUTPUT_FOLDER"] = self.old_output
        if hasattr(app_module, "UPLOAD_DIR") and self.old_upload_dir is not None:
            app_module.UPLOAD_DIR = self.old_upload_dir
        if hasattr(app_module, "OUTPUT_DIR") and self.old_output_dir is not None:
            app_module.OUTPUT_DIR = self.old_output_dir
        self.tmp.cleanup()

    def test_docx_pandoc_uses_workdir_relative_markdown_name(self):
        calls = []
        original_run = app_module.subprocess.run

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            if cmd[0] == "pandoc":
                out_path = Path(cmd[cmd.index("-o") + 1])
                out_path.write_bytes(b"fake docx")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        app_module.subprocess.run = fake_run
        try:
            response = self.client.post(
                "/api/to-docx",
                data={
                    "mdfile": (
                        io.BytesIO("# 标题\n\n正文".encode("utf-8")),
                        "实分析入门（12）--可测函数.md",
                    )
                },
                content_type="multipart/form-data",
            )
        finally:
            app_module.subprocess.run = original_run

        self.assertEqual(response.status_code, 200)
        pandoc_cmd, pandoc_kwargs = calls[0]
        self.assertEqual(pandoc_cmd[1], "实分析入门（12）--可测函数.md")
        self.assertEqual(Path(pandoc_kwargs["cwd"]).resolve().parent, self.upload_dir.resolve())
        self.assertNotIn("uploads", Path(pandoc_cmd[1]).parts)

    def test_rewrite_image_paths_handles_common_local_path_forms(self):
        markdown = "\n".join(
            [
                "![space](images/test%20pic.png)",
                "![angle](<images/test pic.png>)",
                "![rawspace](images/test pic.png)",
                r"![win](images\图 1.png)",
                r'<img src="C:\fakepath\图%201.png" alt="图">',
            ]
        )
        rewritten = app_module.rewrite_image_paths(
            markdown,
            {
                "test pic.png": "test pic.png",
                "图 1.png": "图 1.png",
            },
        )

        self.assertIn("![space](test pic.png)", rewritten)
        self.assertIn("![angle](test pic.png)", rewritten)
        self.assertIn("![rawspace](test pic.png)", rewritten)
        self.assertIn("![win](图 1.png)", rewritten)
        self.assertIn('src="图 1.png"', rewritten)

    def test_safe_name_preserves_chinese_and_strips_windows_invalid_chars(self):
        name = app_module.safe_name(r"C:\Users\alex\实分析:入门?第*1|章.md")

        self.assertIn("实分析", name)
        self.assertNotIn("Users", name)
        self.assertNotRegex(name, r'[\\/:*?"<>|]')

    def test_run_text_uses_default_timeout(self):
        calls = []
        original_run = app_module.subprocess.run

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return subprocess.CompletedProcess(cmd, 0, "", "")

        app_module.subprocess.run = fake_run
        try:
            app_module.run_text(["fake-command"])
        finally:
            app_module.subprocess.run = original_run

        self.assertEqual(calls[0][0], ["fake-command"])
        self.assertEqual(calls[0][1]["timeout"], 120)

    def test_max_upload_mb_parsing_defaults_and_fallbacks(self):
        self.assertEqual(app_module.parse_max_upload_mb(None), 200)
        self.assertEqual(app_module.parse_max_upload_mb(""), 200)
        self.assertEqual(app_module.parse_max_upload_mb("abc"), 200)
        self.assertEqual(app_module.parse_max_upload_mb("0"), 200)
        self.assertEqual(app_module.parse_max_upload_mb("-1"), 200)
        self.assertEqual(app_module.parse_max_upload_mb("64"), 64)

    def test_upload_size_bytes_uses_configured_mb(self):
        self.assertEqual(
            app_module.max_upload_bytes({"MAX_UPLOAD_MB": "32"}),
            32 * 1024 * 1024,
        )
        self.assertEqual(
            app_module.max_upload_bytes({"MAX_UPLOAD_MB": "bad"}),
            200 * 1024 * 1024,
        )

    def test_debug_mode_requires_explicit_env(self):
        self.assertFalse(app_module.debug_enabled({}))
        self.assertFalse(app_module.debug_enabled({"FLASK_DEBUG": "0"}))
        self.assertFalse(app_module.debug_enabled({"FLASK_DEBUG": "false"}))
        self.assertTrue(app_module.debug_enabled({"FLASK_DEBUG": "1"}))
        self.assertTrue(app_module.debug_enabled({"FLASK_DEBUG": "true"}))

    def test_dev_server_uses_safe_local_defaults(self):
        calls = []
        original_run = app_module.app.run
        old_debug = os.environ.pop("FLASK_DEBUG", None)
        old_host = os.environ.pop("APP_HOST", None)
        old_port = os.environ.pop("APP_PORT", None)

        def fake_run(**kwargs):
            calls.append(kwargs)

        app_module.app.run = fake_run
        try:
            app_module.run_server()
        finally:
            app_module.app.run = original_run
            if old_debug is not None:
                os.environ["FLASK_DEBUG"] = old_debug
            if old_host is not None:
                os.environ["APP_HOST"] = old_host
            if old_port is not None:
                os.environ["APP_PORT"] = old_port

        self.assertEqual(calls[0]["port"], 5001)
        self.assertEqual(calls[0]["host"], "127.0.0.1")
        self.assertFalse(calls[0]["debug"])

    def test_dev_server_allows_explicit_debug_host_and_port(self):
        calls = []
        original_run = app_module.app.run
        old_debug = os.environ.get("FLASK_DEBUG")
        old_host = os.environ.get("APP_HOST")
        old_port = os.environ.get("APP_PORT")

        def fake_run(**kwargs):
            calls.append(kwargs)

        os.environ["FLASK_DEBUG"] = "1"
        os.environ["APP_HOST"] = "0.0.0.0"
        os.environ["APP_PORT"] = "5000"
        app_module.app.run = fake_run
        try:
            app_module.run_server()
        finally:
            app_module.app.run = original_run
            for key, old_value in (
                ("FLASK_DEBUG", old_debug),
                ("APP_HOST", old_host),
                ("APP_PORT", old_port),
            ):
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value

        self.assertEqual(calls[0]["port"], 5000)
        self.assertEqual(calls[0]["host"], "0.0.0.0")
        self.assertTrue(calls[0]["debug"])

    def test_frontend_avoids_inner_html_dynamic_rendering(self):
        html = Path(app_module.BASE_DIR / "templates" / "index.html").read_text(encoding="utf-8")

        self.assertNotIn("innerHTML", html)
        self.assertNotIn('onclick="removeImage', html)

    def test_dockerfile_runs_app_as_non_root_user(self):
        dockerfile = Path(app_module.BASE_DIR / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("useradd", dockerfile)
        self.assertIn("USER appuser", dockerfile)
        self.assertIn("chown -R appuser:appuser", dockerfile)

    def test_gitignore_excludes_runtime_and_local_files(self):
        gitignore = Path(app_module.BASE_DIR / ".gitignore").read_text(encoding="utf-8")

        for pattern in ("uploads/", "outputs/", "__pycache__/", "*.pyc", ".venv/", ".env", ".DS_Store"):
            self.assertIn(pattern, gitignore)

    def test_readme_prominently_lists_local_and_docker_urls(self):
        readme = Path(app_module.BASE_DIR / "README.md").read_text(encoding="utf-8")

        self.assertIn("Local Python: http://127.0.0.1:5001", readme)
        self.assertIn("Docker:       http://localhost:5000", readme)

    def test_readme_screenshot_asset_exists(self):
        readme = Path(app_module.BASE_DIR / "README.md").read_text(encoding="utf-8")
        screenshot = Path(app_module.BASE_DIR / "docs" / "screenshot.png")

        self.assertIn("![MD Converter screenshot](docs/screenshot.png)", readme)
        self.assertTrue(screenshot.is_file())
        self.assertGreater(screenshot.stat().st_size, 0)

    def test_to_html_endpoint_is_removed(self):
        response = self.client.post("/api/to-html")

        self.assertEqual(response.status_code, 404)

    def test_pdf_uses_pandoc_supported_highlight_style(self):
        calls = []
        original_run = app_module.subprocess.run
        original_find_chrome = app_module.find_chrome

        def fake_find_chrome():
            return "chrome"

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            if cmd[:2] in (
                ["wkhtmltopdf", "--version"],
                ["md-to-pdf", "--version"],
                ["xelatex", "--version"],
            ):
                return subprocess.CompletedProcess(cmd, 1, "", "")

            if cmd[0] == "pandoc":
                if "--highlight-style=github" in cmd:
                    return subprocess.CompletedProcess(
                        cmd,
                        6,
                        "",
                        "Unknown highlight-style github",
                    )
                out_path = Path(cmd[cmd.index("-o") + 1])
                out_path.write_text("<html><head></head><body>ok</body></html>", encoding="utf-8")
                return subprocess.CompletedProcess(cmd, 0, "", "")

            if cmd[0] == "chrome":
                pdf_arg = next(part for part in cmd if part.startswith("--print-to-pdf="))
                Path(pdf_arg.split("=", 1)[1]).write_bytes(b"%PDF fake")
                return subprocess.CompletedProcess(cmd, 0, "", "")

            return subprocess.CompletedProcess(cmd, 1, "", "")

        app_module.find_chrome = fake_find_chrome
        app_module.subprocess.run = fake_run
        try:
            response = self.client.post(
                "/api/to-pdf",
                data={
                    "mdfile": (
                        io.BytesIO("```python\nprint(1)\n```".encode("utf-8")),
                        "code.md",
                    )
                },
                content_type="multipart/form-data",
            )
        finally:
            app_module.subprocess.run = original_run
            app_module.find_chrome = original_find_chrome

        self.assertEqual(response.status_code, 200)
        pandoc_calls = [cmd for cmd, _ in calls if cmd[0] == "pandoc"]
        self.assertTrue(pandoc_calls)
        self.assertNotIn("--highlight-style=github", pandoc_calls[0])

    def test_pdf_prefers_xelatex_before_wkhtmltopdf(self):
        calls = []
        original_run = app_module.subprocess.run
        original_command_available = app_module.command_available
        original_find_chrome = app_module.find_chrome

        def fake_command_available(command):
            return command in {"xelatex", "wkhtmltopdf"}

        def fake_find_chrome():
            return None

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            if cmd[0] == "pandoc" and "--pdf-engine=xelatex" in cmd:
                out_path = Path(cmd[cmd.index("-o") + 1])
                out_path.write_bytes(b"%PDF xelatex")
                return subprocess.CompletedProcess(cmd, 0, "", "")
            if cmd[0] == "wkhtmltopdf":
                out_path = Path(cmd[-1])
                out_path.write_bytes(b"%PDF wkhtmltopdf")
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return subprocess.CompletedProcess(cmd, 1, "", "unexpected command")

        app_module.command_available = fake_command_available
        app_module.find_chrome = fake_find_chrome
        app_module.subprocess.run = fake_run
        try:
            response = self.client.post(
                "/api/to-pdf",
                data={
                    "mdfile": (
                        io.BytesIO("$$x^2$$".encode("utf-8")),
                        "math.md",
                    )
                },
                content_type="multipart/form-data",
            )
        finally:
            app_module.subprocess.run = original_run
            app_module.command_available = original_command_available
            app_module.find_chrome = original_find_chrome

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[:12], b"%PDF xelatex")
        generation_cmds = [
            cmd for cmd, _ in calls
            if isinstance(cmd, list) and cmd and cmd[0] in {"pandoc", "wkhtmltopdf"}
        ]
        self.assertEqual(generation_cmds[0][0], "pandoc")
        self.assertIn("--pdf-engine=xelatex", generation_cmds[0])
        self.assertFalse(any(cmd[0] == "wkhtmltopdf" for cmd in generation_cmds))

    def test_pdf_xelatex_tries_next_cjk_font_when_first_font_fails(self):
        calls = []
        original_run = app_module.subprocess.run
        original_command_available = app_module.command_available
        original_find_chrome = app_module.find_chrome
        original_weasyprint = app_module.render_pdf_with_weasyprint
        old_font = os.environ.get("PDF_CJK_FONT")

        def fake_command_available(command):
            return command == "xelatex"

        def fake_find_chrome():
            return None

        def fake_weasyprint(html_path, out_path):
            return False, "weasyprint disabled"

        def cjk_font(cmd):
            for index, part in enumerate(cmd):
                if part == "-V" and index + 1 < len(cmd):
                    value = cmd[index + 1]
                    if value.startswith("CJKmainfont="):
                        return value.split("=", 1)[1]
            return None

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            if cmd[0] == "pandoc" and "--pdf-engine=xelatex" in cmd:
                font = cjk_font(cmd)
                if font == "Broken Font":
                    return subprocess.CompletedProcess(cmd, 43, "", "font not found")
                out_path = Path(cmd[cmd.index("-o") + 1])
                out_path.write_bytes(b"%PDF fallback font")
                return subprocess.CompletedProcess(cmd, 0, "", "")
            if cmd[0] == "pandoc":
                out_path = Path(cmd[cmd.index("-o") + 1])
                out_path.write_text("<html><head></head><body>ok</body></html>", encoding="utf-8")
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return subprocess.CompletedProcess(cmd, 1, "", "unexpected command")

        os.environ["PDF_CJK_FONT"] = "Broken Font"
        app_module.command_available = fake_command_available
        app_module.find_chrome = fake_find_chrome
        app_module.render_pdf_with_weasyprint = fake_weasyprint
        app_module.subprocess.run = fake_run
        try:
            response = self.client.post(
                "/api/to-pdf",
                data={
                    "mdfile": (
                        io.BytesIO("# title".encode("utf-8")),
                        "font.md",
                    )
                },
                content_type="multipart/form-data",
            )
        finally:
            app_module.subprocess.run = original_run
            app_module.command_available = original_command_available
            app_module.find_chrome = original_find_chrome
            app_module.render_pdf_with_weasyprint = original_weasyprint
            if old_font is None:
                os.environ.pop("PDF_CJK_FONT", None)
            else:
                os.environ["PDF_CJK_FONT"] = old_font

        self.assertEqual(response.status_code, 200)
        xelatex_calls = [
            cmd for cmd, _ in calls
            if cmd[0] == "pandoc" and "--pdf-engine=xelatex" in cmd
        ]
        fonts = [cjk_font(cmd) for cmd in xelatex_calls]
        self.assertGreaterEqual(len(fonts), 2)
        self.assertEqual(fonts[0], "Broken Font")
        self.assertNotEqual(fonts[1], "Broken Font")

    def test_pdf_falls_back_to_weasyprint_when_chrome_fails(self):
        original_run = app_module.subprocess.run
        original_find_chrome = app_module.find_chrome
        had_weasyprint = hasattr(app_module, "render_pdf_with_weasyprint")
        original_weasyprint = getattr(app_module, "render_pdf_with_weasyprint", None)

        def fake_find_chrome():
            return "chrome"

        def fake_weasyprint(html_path, out_path):
            Path(out_path).write_bytes(b"%PDF weasyprint")
            return True, ""

        def fake_run(cmd, **kwargs):
            if cmd[:2] in (
                ["wkhtmltopdf", "--version"],
                ["md-to-pdf", "--version"],
                ["xelatex", "--version"],
            ):
                return subprocess.CompletedProcess(cmd, 1, "", "")

            if cmd[0] == "pandoc" and "--embed-resources" in cmd:
                out_path = Path(cmd[cmd.index("-o") + 1])
                out_path.write_text("<html><head></head><body>ok</body></html>", encoding="utf-8")
                return subprocess.CompletedProcess(cmd, 0, "", "")

            if cmd[0] == "chrome":
                return subprocess.CompletedProcess(cmd, 1, "", "CreateFile: access denied")

            return subprocess.CompletedProcess(cmd, 1, "", "missing engine")

        app_module.find_chrome = fake_find_chrome
        app_module.subprocess.run = fake_run
        app_module.render_pdf_with_weasyprint = fake_weasyprint
        try:
            response = self.client.post(
                "/api/to-pdf",
                data={
                    "mdfile": (
                        io.BytesIO("# fallback".encode("utf-8")),
                        "fallback.md",
                    )
                },
                content_type="multipart/form-data",
            )
        finally:
            app_module.subprocess.run = original_run
            app_module.find_chrome = original_find_chrome
            if had_weasyprint:
                app_module.render_pdf_with_weasyprint = original_weasyprint
            else:
                delattr(app_module, "render_pdf_with_weasyprint")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[:4], b"%PDF")

    def test_check_deps_reports_xelatex(self):
        original_command_available = app_module.command_available
        original_find_chrome = app_module.find_chrome

        def fake_command_available(command):
            return command == "xelatex"

        app_module.command_available = fake_command_available
        app_module.find_chrome = lambda: None
        try:
            response = self.client.get("/api/check-deps")
        finally:
            app_module.command_available = original_command_available
            app_module.find_chrome = original_find_chrome

        self.assertEqual(response.status_code, 200)
        self.assertIn("xelatex", response.json)
        self.assertTrue(response.json["xelatex"])


if __name__ == "__main__":
    unittest.main()
