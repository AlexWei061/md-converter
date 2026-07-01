# AGENTS.md

## Project Overview

This repository is a local-first document conversion web tool built with Flask, MarkItDown, and Pandoc.

The project supports two main workflows:

1. Convert common document formats to Markdown.
2. Convert Markdown to Word or PDF, including Markdown files that reference local images.

The intended positioning is:

> A local-first Markdown document conversion workbench, especially useful for Chinese documents, academic notes, AI preprocessing, and Markdown-to-Word/PDF export.

This project should not be treated as a production-ready public SaaS service without additional sandboxing, authentication, queueing, rate limits, and resource isolation.

## Core Stack

* Backend: Python + Flask
* Document to Markdown: MarkItDown
* Markdown to Word/PDF: Pandoc
* Preferred PDF engine: Pandoc + XeLaTeX
* PDF fallback engines: Chrome headless, WeasyPrint, wkhtmltopdf, md-to-pdf, Pandoc default engine
* Frontend: plain HTML/CSS/JavaScript in `templates/index.html`
* Tests: Python `unittest`

## Repository Structure

Expected structure:

```text
md-converter/
├── app.py
├── requirements.txt
├── README.md
├── AGENTS.md
├── templates/
│   └── index.html
├── tests/
│   └── test_app_paths.py
├── uploads/
└── outputs/
```

`uploads/` and `outputs/` are runtime directories and should not be committed with user-generated files.

## Key Features to Preserve

Do not remove or regress these behaviors:

* File to Markdown conversion through `/api/to-markdown`
* Markdown to Word conversion through `/api/to-docx`
* Markdown to PDF conversion through `/api/to-pdf`
* Dependency status detection through `/api/check-deps`
* Chinese filename handling
* Local image support for Markdown export
* HTML image tag support, including tags like:

```html
<img src="./pic/example.png" style="zoom:33%;" />
```

* Markdown image path rewriting for common forms:

  * `![](img/a.png)`
  * `![](<img/a b.png>)`
  * `test%20pic.png`
  * Windows-style paths such as `images\chart.png`
  * HTML `<img src="...">` tags

## Backend Development Guidelines

### General Rules

* Keep the Flask routes compatible with the current frontend.
* Do not rename existing API endpoints unless the frontend and README are updated together.
* Prefer small, targeted changes over large rewrites.
* Keep the project usable as a local tool with `python app.py`.
* Do not introduce a database unless absolutely necessary.
* Do not add external cloud services or API keys.
* Do not require user login for the local version.
* Do not silently upload user documents to third-party services.

### File Handling

The project handles potentially sensitive documents. Treat uploaded files carefully.

Required principles:

* Sanitize filenames.
* Avoid trusting user-provided paths.
* Keep all temporary files inside configured upload/output directories.
* Clean temporary files after conversion.
* Do not expose local filesystem paths in user-facing errors.
* Do not keep converted documents longer than needed.
* Avoid adding new file formats unless there is a clear reason.

If adding public or multi-user deployment support, first add:

* Authentication
* Per-user isolation
* File size limits
* Conversion timeouts
* Background job queue
* Rate limiting
* Sandboxed conversion workers
* Periodic cleanup
* Clear privacy notice

### External Commands

The project uses external commands such as:

* `markitdown`
* `pandoc`
* `xelatex`
* `wkhtmltopdf`
* `md-to-pdf`
* Chrome / Chromium

When modifying command execution:

* Use argument arrays, not shell strings.
* Do not use `shell=True`.
* Always keep timeouts.
* Capture stdout/stderr safely.
* Return helpful but not overly verbose errors.
* Do not leak full internal paths or stack traces to users.

### PDF Export

PDF export has several fallback engines. Preserve the intended priority:

1. Pandoc + XeLaTeX
2. Chrome headless
3. WeasyPrint
4. wkhtmltopdf
5. md-to-pdf
6. Pandoc default PDF engine

For Chinese documents and math-heavy Markdown, Pandoc + XeLaTeX should remain the preferred path.

If modifying PDF behavior, test:

* Chinese text
* English text
* Headings
* Tables
* Code blocks
* Local images
* Basic LaTeX math
* HTML image tags

## Frontend Development Guidelines

The frontend is intentionally simple and dependency-free.

### General Rules

* Do not introduce a frontend framework unless explicitly requested.
* Preserve the two-panel workflow:

  * Left: file to Markdown
  * Right: Markdown to Word/PDF
* Keep drag-and-drop upload behavior.
* Keep dependency status indicators.
* Keep copy, download, and send-to-right actions.

### Security

Avoid unsafe HTML injection.

Do not directly insert user-controlled content into `innerHTML`.

Prefer:

* `textContent`
* `createElement`
* `appendChild`
* DOM APIs

Only use `innerHTML` for fully controlled static UI fragments. If a string includes filenames, backend errors, Markdown content, or user-provided data, render it safely as text.

### User Experience

When improving the UI:

* Keep error messages clear and actionable.
* Tell users which dependency is missing when conversion fails.
* Do not overwhelm users with low-level stack traces.
* Prefer specific hints, such as:

  * “Pandoc is not installed.”
  * “XeLaTeX is missing. PDF export will try fallback engines.”
  * “Upload the image files referenced by your Markdown.”

## Testing

Use the current test style unless there is a strong reason to change it.

Recommended command:

```bash
python -m unittest discover -s tests
```

Before submitting changes, run tests locally when possible.

Important behaviors to test:

* Chinese filename preservation
* Filename sanitization
* Markdown image path rewriting
* HTML image path rewriting
* DOCX generation command construction
* PDF engine priority
* PDF fallback behavior
* Dependency detection
* Removed endpoints should remain removed if intentionally deleted

## Documentation Guidelines

README changes should stay practical and user-facing.

The README should clearly explain:

* What the project does
* Who it is for
* Local-first positioning
* Supported conversions
* Required system dependencies
* Python dependency installation
* How to start the app
* How local images are handled
* PDF engine priority
* Why public SaaS deployment needs extra safety work

Do not claim the project is production-ready for public SaaS unless the necessary security and scaling work has been implemented.

## Deployment Guidance

The default supported deployment mode is local or trusted internal network usage.

Safe default:

```bash
python app.py
```

or, if Docker support exists:

```bash
docker compose up
```

For public deployment, additional hardening is required. At minimum:

* Disable debug mode
* Use a production WSGI server
* Add authentication
* Add request size limits
* Add rate limits
* Isolate conversion jobs
* Clean temporary files periodically
* Run the app as a non-root user
* Avoid mounting sensitive host directories
* Add logging and monitoring

## Coding Style

* Prefer readable Python over clever abstractions.
* Keep helper functions small.
* Use clear names.
* Keep comments useful and factual.
* Avoid broad exception swallowing unless returning a controlled user-facing error.
* Do not add unnecessary dependencies.
* Do not mix unrelated changes in one commit.

## Release Checklist

Before a public release:

* [ ] App does not run with debug mode enabled by default.
* [ ] README explains local-first positioning.
* [ ] README warns against unsafe public deployment.
* [ ] License file exists.
* [ ] Docker usage is documented if Docker support is added.
* [ ] Tests pass.
* [ ] Temporary files are cleaned after conversions.
* [ ] Frontend does not inject user-controlled strings through `innerHTML`.
* [ ] Dependency detection works.
* [ ] Markdown with local images exports correctly.
* [ ] Chinese Markdown exports to PDF correctly when XeLaTeX and Chinese fonts are installed.
* [ ] Error messages are understandable to non-developers.

## What Not to Do

Do not:

* Convert the project into a large SaaS platform prematurely.
* Add user accounts, payments, or cloud storage without explicit product direction.
* Upload user files to external services.
* Remove local-first usability.
* Break existing API routes.
* Replace the simple frontend with a heavy framework without a clear reason.
* Commit generated files from `uploads/` or `outputs/`.
* Commit secrets, API keys, or private documents.
