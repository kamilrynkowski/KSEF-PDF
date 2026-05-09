from __future__ import annotations

import io
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from flask import Flask, render_template, request, send_file
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from .extractor import ensure_unique_filename, extract_invoice_data, make_target_filename

ALLOWED_EXTENSIONS = {".pdf"}


@dataclass
class RenameResult:
    original_name: str
    target_name: str
    status: str
    message: str


def create_app() -> Flask:
    app = Flask(__name__, template_folder="../../templates")
    app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

    @app.get("/")
    def index():
        return render_template("index.html", results=None)

    @app.post("/preview")
    def preview():
        files = _uploaded_pdf_files(request.files.getlist("files"))
        results = [_analyse_upload(file) for file in files]
        return render_template("index.html", results=results)

    @app.post("/download")
    def download():
        files = _uploaded_pdf_files(request.files.getlist("files"))
        zip_buffer = io.BytesIO()
        used_names: set[str] = set()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in files:
                target_name = _target_name_for_upload(file, used_names)
                used_names.add(target_name)
                file.stream.seek(0)
                archive.writestr(target_name, file.read())

        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name="ksef_pdf_po_zmianie_nazw.zip",
        )

    return app


def _uploaded_pdf_files(files: list[FileStorage]) -> list[FileStorage]:
    return [file for file in files if file and Path(file.filename or "").suffix.lower() in ALLOWED_EXTENSIONS]


def _analyse_upload(file: FileStorage) -> RenameResult:
    try:
        target_name = _target_name_for_upload(file, set())
        return RenameResult(file.filename or "plik.pdf", target_name, "ok", "Gotowe")
    except Exception as exc:  # noqa: BLE001 - surface per-file parsing errors in the UI
        fallback = secure_filename(file.filename or "plik.pdf") or "plik.pdf"
        return RenameResult(file.filename or fallback, fallback, "error", str(exc))
    finally:
        file.stream.seek(0)


def _target_name_for_upload(file: FileStorage, used_names: set[str]) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        file.stream.seek(0)
        file.save(tmp.name)
        data = extract_invoice_data(tmp.name)
        target_name = make_target_filename(data)
    return ensure_unique_filename(target_name, used_names)


app = create_app()
