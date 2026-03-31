"""Validation helpers for seller-managed uploads and external file links."""

from __future__ import annotations

from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


MAX_PRODUCT_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMPORT_CSV_BYTES = 2 * 1024 * 1024
MAX_EXTERNAL_IMAGE_URLS = 10

_ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
_ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}
_ALLOWED_CSV_CONTENT_TYPES = {
    "",
    "application/csv",
    "application/vnd.ms-excel",
    "text/csv",
    "text/plain",
}
_URL_VALIDATOR = URLValidator(schemes=["http", "https"])


def _normalized_extension(filename: str) -> str:
    raw_name = (filename or "").strip()
    if "." not in raw_name:
        return ""
    return raw_name.rsplit(".", 1)[-1].lower()


def _detect_image_format(header: bytes) -> str:
    if header.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    return ""


def validate_product_image_upload(upload) -> str:
    """Validate uploaded product image and return normalized extension."""
    if upload is None:
        raise ValidationError("Файл изображения не передан")

    if int(getattr(upload, "size", 0) or 0) <= 0:
        raise ValidationError("Файл изображения пустой")
    if int(upload.size) > MAX_PRODUCT_IMAGE_BYTES:
        raise ValidationError("Изображение должно быть не больше 5 МБ")

    extension = _normalized_extension(getattr(upload, "name", ""))
    if extension not in _ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError("Поддерживаются только JPG, PNG и WEBP изображения")

    content_type = (getattr(upload, "content_type", "") or "").strip().lower()
    if content_type and content_type not in _ALLOWED_IMAGE_CONTENT_TYPES:
        raise ValidationError("Формат изображения не поддерживается")

    header = upload.read(16)
    upload.seek(0)
    detected = _detect_image_format(header)
    if not detected:
        raise ValidationError("Файл не распознан как безопасное изображение")
    if detected == "jpeg" and extension not in {"jpg", "jpeg"}:
        raise ValidationError("Расширение файла не соответствует содержимому изображения")
    if detected != "jpeg" and detected != extension:
        raise ValidationError("Расширение файла не соответствует содержимому изображения")
    return "jpg" if detected == "jpeg" else detected


def validate_http_url(value: str, *, field_label: str) -> str:
    """Validate external HTTP(S) URL used in seller forms."""
    normalized = (value or "").strip()
    if not normalized:
        return ""
    _URL_VALIDATOR(normalized)
    parsed = urlsplit(normalized)
    if not parsed.netloc:
        raise ValidationError(f"{field_label} должен содержать полный URL")
    return normalized


def validate_product_image_urls(values: list[str]) -> list[str]:
    """Validate linked product image URLs and enforce a sane upper bound."""
    normalized_values = []
    for value in values or []:
        normalized_values.append(validate_http_url(value, field_label="Ссылка на изображение"))
    if len(normalized_values) > MAX_EXTERNAL_IMAGE_URLS:
        raise ValidationError("Можно указать не больше 10 ссылок на изображения")
    return normalized_values


def validate_csv_upload(upload):
    """Validate CSV upload by size, mime, extension and readable header row."""
    if upload is None:
        raise ValidationError("CSV файл не передан")
    if int(getattr(upload, "size", 0) or 0) <= 0:
        raise ValidationError("CSV файл пустой")
    if int(upload.size) > MAX_IMPORT_CSV_BYTES:
        raise ValidationError("CSV файл должен быть не больше 2 МБ")

    filename = (getattr(upload, "name", "") or "").strip().lower()
    if not filename.endswith(".csv"):
        raise ValidationError("Поддерживается только CSV шаблон")

    content_type = (getattr(upload, "content_type", "") or "").strip().lower()
    if content_type not in _ALLOWED_CSV_CONTENT_TYPES:
        raise ValidationError("Неверный content-type для CSV файла")

    sample = upload.read(2048)
    upload.seek(0)
    try:
        preview = sample.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError("CSV файл должен быть в UTF-8") from exc

    first_line = next((line for line in preview.splitlines() if line.strip()), "")
    if "," not in first_line:
        raise ValidationError("CSV файл должен содержать строку заголовков через запятую")
    return upload
