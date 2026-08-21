import requests
from pathlib import Path


# ROOT default project
PROJECT_ROOT = Path.home() / "whatsapp-ai"


def safe_path(path: str) -> Path:
    """
    Mendukung path relatif (terhadap project)
    maupun path absolut / di luar project.
    """
    p = Path(path).expanduser()
    if p.is_absolute():
        return p.resolve()
    return (PROJECT_ROOT / path).resolve()


def list_files(path: str = ".") -> str:

    directory = safe_path(path)

    if not directory.exists():
        return f"Folder tidak ditemukan: {path}"

    if not directory.is_dir():
        return f"Bukan folder: {path}"

    files = []

    for item in sorted(directory.iterdir()):
        if item.is_dir():
            files.append(f"[DIR]  {item.name}")
        else:
            files.append(f"[FILE] {item.name}")

    if not files:
        return "(folder kosong)"

    return "\n".join(files)


def read_file(path: str) -> str:

    file_path = safe_path(path)

    if not file_path.exists():
        return f"File tidak ditemukan: {path}"

    if not file_path.is_file():
        return f"Bukan file: {path}"

    return file_path.read_text(encoding="utf-8")


def write_file(path: str, content: str) -> str:

    file_path = safe_path(path)

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    file_path.write_text(
        content,
        encoding="utf-8"
    )

    return f"File berhasil dibuat/ditulis: {path}"


def edit_file(
    path: str,
    old_text: str,
    new_text: str
) -> str:

    file_path = safe_path(path)

    if not file_path.exists():
        return f"File tidak ditemukan: {path}"

    content = file_path.read_text(
        encoding="utf-8"
    )

    if old_text not in content:
        return "Teks yang ingin diganti tidak ditemukan."

    content = content.replace(
        old_text,
        new_text,
        1
    )

    file_path.write_text(
        content,
        encoding="utf-8"
    )

    return f"File berhasil diedit: {path}"


def delete_file(path: str) -> str:

    file_path = safe_path(path)

    if not file_path.exists():
        return f"File tidak ditemukan: {path}"

    if file_path.is_dir():
        return "Penghapusan folder tidak diizinkan."

    file_path.unlink()

    return f"File berhasil dihapus: {path}"


def download_file(url: str, path: str) -> str:
    """
    Mendownload file dari URL luar dan menyimpannya ke path lokal.
    """
    try:
        file_path = safe_path(path)
        file_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        response = requests.get(
            url,
            timeout=60,
            stream=True
        )
        response.raise_for_status()

        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return f"File berhasil didownload dari {url} dan disimpan ke: {path}"

    except Exception as error:
        return f"Gagal mendownload file dari {url}: {error}"

