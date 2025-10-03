from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Tuple

# Armazena imagens localmente (MVP). Em produção, prefira S3/GCS com URLs assinadas.

UPLOAD_ROOT = Path("uploads")
UPLOAD_IMOVEIS_DIR = UPLOAD_ROOT / "imoveis"

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def ensure_base_dirs() -> None:
    UPLOAD_IMOVEIS_DIR.mkdir(parents=True, exist_ok=True)


def _guess_ext_from_name(name: str | None) -> str | None:
    if not name:
        return None
    n = name.lower()
    if n.endswith(".jpeg") or n.endswith(".jpg"):
        return ".jpg"
    if n.endswith(".png"):
        return ".png"
    if n.endswith(".webp"):
        return ".webp"
    return None


def save_property_images(
    property_id: int,
    files: List[any],  # FastAPI UploadFile-like (possui .filename, .content_type, .file)
) -> List[Tuple[str, Path]]:
    """
    Salva os arquivos em uploads/imoveis/{property_id}/ e retorna lista de tuplas
    (filename, full_path) para cada arquivo salvo.
    """
    ensure_base_dirs()
    target_dir = UPLOAD_IMOVEIS_DIR / str(property_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    saved: List[Tuple[str, Path]] = []

    import time

    for idx, f in enumerate(files):
        # Determinar extensão segura
        ext = None
        ct = (getattr(f, "content_type", None) or "").lower()
        if ct == "image/jpeg":
            ext = ".jpg"
        elif ct == "image/png":
            ext = ".png"
        elif ct == "image/webp":
            ext = ".webp"
        if not ext:
            ext = _guess_ext_from_name(getattr(f, "filename", None))
        if not ext or ext not in ALLOWED_EXTS:
            raise ValueError(f"unsupported_type:{ct or getattr(f, 'filename', '')}")

        safe_name = f"{int(time.time() * 1000)}_{idx}{ext}"
        file_path = target_dir / safe_name

        with file_path.open("wb") as out:
            while True:
                chunk = f.file.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        try:
            f.file.close()
        except Exception:
            pass

        saved.append((safe_name, file_path))

    return saved
