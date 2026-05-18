import os
import mimetypes
from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_NF_EXT = {"png", "jpg", "jpeg", "webp", "pdf"}

def _ensure_nf_upload_folder():
    folder = current_app.config.get("NF_UPLOAD_FOLDER")
    if not folder:
        folder = os.path.join(current_app.root_path, "static", "uploads", "nf")
        current_app.config["NF_UPLOAD_FOLDER"] = folder
    os.makedirs(folder, exist_ok=True)
    return folder

def _allowed_nf_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_NF_EXT

def _save_nf_file(file_storage, equipment_id: int) -> tuple[str, str]:
    _ensure_nf_upload_folder()
    original = file_storage.filename or ""
    if not original:
        raise ValueError("missing_filename")
    if not _allowed_nf_file(original):
        raise ValueError("invalid_ext")
    safe = secure_filename(original)
    ext = safe.rsplit(".", 1)[1].lower()
    final_name = f"nf_{equipment_id}.{ext}"
    folder = current_app.config["NF_UPLOAD_FOLDER"]
    save_path = os.path.join(folder, final_name)
    file_storage.save(save_path)
    mime = (file_storage.mimetype or "").strip()
    if not mime:
        mime = mimetypes.guess_type(final_name)[0] or None
    return final_name, mime

def _delete_nf_file(filename: str | None):
    if not filename:
        return
    folder = current_app.config.get("NF_UPLOAD_FOLDER") or os.path.join(
        current_app.root_path, "static", "uploads", "nf"
    )
    path = os.path.join(folder, filename)
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
