import os
import re
import shutil
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List

from core import ensure_dirs, error_response, success_response

SUPPORTED_EXTENSIONS = {'.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff'}
DEFAULT_TESSERACT_PATHS = [
    Path(r'C:\Program Files\Tesseract-OCR\tesseract.exe'),
    Path(r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'),
]


def _validate_image_path(image_path: str) -> Path:
    path = Path(image_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f'File gambar tidak ditemukan: {path}')
    if not path.is_file():
        raise ValueError(f'Path bukan file: {path}')
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f'Format gambar tidak didukung: {path.suffix.lower()}')
    return path


def _find_tesseract() -> Path:
    env_path = os.environ.get('TESSERACT_CMD')
    if env_path and Path(env_path).exists():
        return Path(env_path).resolve()
    executable = shutil.which('tesseract') or shutil.which('tesseract.exe')
    if executable:
        return Path(executable).resolve()
    for candidate in DEFAULT_TESSERACT_PATHS:
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError(
        'Tesseract OCR tidak ditemukan. Install Tesseract OCR atau set '
        'environment variable TESSERACT_CMD ke lokasi tesseract.exe.'
    )


def _load_dependencies():
    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    except ImportError as exc:
        raise RuntimeError('Install Pillow: py -m pip install pillow') from exc
    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError('Install pytesseract: py -m pip install pytesseract') from exc
    return Image, ImageEnhance, ImageFilter, ImageOps, pytesseract


def _preprocess(image, mode, scale, ImageEnhance, ImageFilter, ImageOps):
    mode = (mode or 'none').lower()
    if scale <= 0:
        raise ValueError('Scale harus lebih besar dari 0.')
    if scale != 1.0:
        image = image.resize((max(1, int(image.width*scale)), max(1, int(image.height*scale))))
    if mode == 'none':
        return image
    gray = ImageOps.grayscale(image)
    if mode == 'grayscale':
        return gray
    if mode == 'contrast':
        return ImageEnhance.Contrast(gray).enhance(2.0)
    if mode == 'sharpen':
        return gray.filter(ImageFilter.SHARPEN)
    if mode == 'threshold':
        gray = ImageEnhance.Contrast(gray).enhance(2.0)
        return gray.point(lambda v: 255 if v > 160 else 0)
    raise ValueError('Mode preprocess: none, grayscale, contrast, sharpen, threshold')


def _trim_text(text: str, max_chars: int) -> Dict[str, Any]:
    original = len(text)
    if max_chars <= 0 or original <= max_chars:
        return {'text': text, 'truncated': False, 'original_char_count': original, 'returned_char_count': original}
    trimmed = text[:max_chars]
    return {'text': trimmed, 'truncated': True, 'original_char_count': original, 'returned_char_count': len(trimmed)}


def list_ocr_languages():
    tool_name = 'list_ocr_languages'
    try:
        _, _, _, _, pytesseract = _load_dependencies()
        tesseract = _find_tesseract()
        pytesseract.pytesseract.tesseract_cmd = str(tesseract)
        languages = pytesseract.get_languages(config='')
        return success_response(tool=tool_name, message='Daftar bahasa OCR berhasil dibaca', extra={
            'tesseract_path': str(tesseract), 'languages': languages, 'language_count': len(languages)
        })
    except Exception as exc:
        return error_response(tool_name, exc)


def read_image_text(image_path: str, lang: str='eng', preprocess: str='grayscale', scale: float=1.5,
                    psm: int=6, max_chars: int=50000, include_words: bool=True):
    tool_name = 'read_image_text'
    try:
        ensure_dirs()
        path = _validate_image_path(image_path)
        Image, ImageEnhance, ImageFilter, ImageOps, pytesseract = _load_dependencies()
        tesseract = _find_tesseract()
        pytesseract.pytesseract.tesseract_cmd = str(tesseract)
        available = pytesseract.get_languages(config='')
        requested = [x.strip() for x in lang.split('+') if x.strip()]
        missing = [x for x in requested if x not in available]
        if missing:
            raise ValueError(f'Bahasa OCR belum terpasang: {missing}. Tersedia: {available}')
        if not 0 <= psm <= 13:
            raise ValueError('PSM harus 0 sampai 13.')

        with Image.open(path) as original:
            original_size = {'width': original.width, 'height': original.height}
            processed = _preprocess(original.convert('RGB'), preprocess, scale, ImageEnhance, ImageFilter, ImageOps)
            processed_size = {'width': processed.width, 'height': processed.height}
            config = f'--psm {psm}'
            text = pytesseract.image_to_string(processed, lang=lang, config=config).strip()
            words: List[Dict[str, Any]] = []
            confidences = []
            if include_words:
                data = pytesseract.image_to_data(processed, lang=lang, config=config, output_type=pytesseract.Output.DICT)
                for i, word in enumerate(data.get('text', [])):
                    word = str(word).strip()
                    if not word:
                        continue
                    try:
                        conf = float(data['conf'][i])
                    except Exception:
                        conf = -1.0
                    words.append({
                        'text': word, 'confidence': conf,
                        'left': int(data['left'][i]), 'top': int(data['top'][i]),
                        'width': int(data['width'][i]), 'height': int(data['height'][i]),
                        'line_num': int(data['line_num'][i]),
                    })
                    if conf >= 0:
                        confidences.append(conf)
            avg_conf = sum(confidences)/len(confidences) if confidences else None

        trimmed = _trim_text(text, max_chars)
        return success_response(tool=tool_name, message='Teks pada gambar berhasil dibaca', extra={
            'file_path': str(path), 'file_type': path.suffix.lower(),
            'tesseract_path': str(tesseract), 'language': lang,
            'available_languages': available, 'preprocess': preprocess,
            'scale': scale, 'psm': psm,
            'original_size': original_size, 'processed_size': processed_size,
            'average_confidence': avg_conf, 'word_count': len(words),
            'words': words if include_words else [], **trimmed,
        })
    except Exception as exc:
        return error_response(tool_name, exc)
