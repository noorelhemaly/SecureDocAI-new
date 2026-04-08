#!/usr/bin/env python3
"""
Qwen2.5-VL OCR Module

Wraps the local Qwen2.5-VL-3B-Instruct vision-language model for high-quality
OCR on images and scanned documents (Arabic + English).

The model is loaded lazily on first use and cached for the session.
Falls back gracefully if torch/transformers are not installed.
"""

import os
import re
import time
from pathlib import Path
from typing import Optional

# Model directory — can be overridden via QWEN_OCR_MODEL_DIR env var
_DEFAULT_MODEL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models"
)
MODEL_DIR = os.environ.get("QWEN_OCR_MODEL_DIR", _DEFAULT_MODEL_DIR)

# Image resolution cap passed to the processor.
# 1280*28*28 (~1M pixels) gives the best accuracy for Arabic ID cards/passports.
# Override via QWEN_MAX_PIXELS env var (integer).
_DEFAULT_MAX_PIXELS = 1280 * 28 * 28
MAX_PIXELS = int(os.environ.get("QWEN_MAX_PIXELS", _DEFAULT_MAX_PIXELS))

# Prompts
MIXED_PROMPT = (
    "Extract all Arabic and English text from this image completely from beginning to end. "
    "Read every word exactly as written, without adding or removing anything:"
)
ARABIC_PROMPT = (
    "أرجو استخراج النص العربي كاملاً من هذه الصورة من البداية الى النهاية "
    "بدون اي اختصار ودون زيادة او حذف. اقرأ كل المحتوى النصي الموجود في الصورة:"
)
ENGLISH_PROMPT = "Extract all English text from this image exactly as written:"

# Lazy-loaded globals
_model = None
_processor = None
_load_error: Optional[str] = None
_loaded = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import transformers  # noqa: F401
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

QWEN_AVAILABLE = TORCH_AVAILABLE and TRANSFORMERS_AVAILABLE


def is_available() -> bool:
    """Return True if the Qwen OCR model can be loaded."""
    if not QWEN_AVAILABLE:
        return False
    config_path = os.path.join(MODEL_DIR, "config.json")
    if not os.path.exists(config_path):
        return False
    return True


def _load_model():
    """Load the Qwen2.5-VL model and processor (called once, cached)."""
    global _model, _processor, _load_error, _loaded
    if _loaded:
        return
    _loaded = True

    if not QWEN_AVAILABLE:
        _load_error = "torch or transformers not installed"
        return

    config_path = os.path.join(MODEL_DIR, "config.json")
    if not os.path.exists(config_path):
        _load_error = f"Model not found at {MODEL_DIR}"
        return

    try:
        import torch
        from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32

        print(f"[QwenOCR] Loading model from {MODEL_DIR} on {device}...")
        t0 = time.time()

        _processor = AutoProcessor.from_pretrained(
            MODEL_DIR,
            trust_remote_code=True,
            local_files_only=True,
        )

        _model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            MODEL_DIR,
            torch_dtype=dtype,
            device_map=device,
            trust_remote_code=True,
            local_files_only=True,
        )
        _model.eval()
        print(f"[QwenOCR] Model loaded in {time.time() - t0:.1f}s")

    except Exception as e:
        _load_error = str(e)
        print(f"[QwenOCR] Failed to load model: {e}")


def ocr_image(image, prompt: Optional[str] = None, max_tokens: int = 256) -> str:
    """
    Run Qwen OCR on a PIL Image.

    Args:
        image: PIL.Image.Image
        prompt: OCR prompt (defaults to mixed Arabic+English)
        max_tokens: Maximum tokens to generate

    Returns:
        Extracted text string (empty string on failure)
    """
    _load_model()

    if _model is None or _processor is None:
        return ""

    if prompt is None:
        prompt = MIXED_PROMPT

    try:
        import torch

        image_rgb = image.convert("RGB") if image.mode != "RGB" else image

        messages = [{"role": "user", "content": [
            {"type": "image", "image": image_rgb},
            {"type": "text", "text": prompt},
        ]}]

        t_pre = time.time()
        text_input = _processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = _processor(
            text=[text_input],
            images=[image_rgb],
            padding=True,
            return_tensors="pt",
            # Cap image resolution — default 1280*28*28 is very slow on CPU;
            # 512*28*28 is sufficient for documents and ~2x faster.
            max_pixels=MAX_PIXELS,
        ).to(_model.device)
        print(f"[QwenOCR] Preprocessing: {time.time() - t_pre:.1f}s  "
              f"| input tokens: {inputs.input_ids.shape[1]}")

        t_gen = time.time()
        with torch.no_grad():
            gen_ids = _model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                do_sample=False,
                repetition_penalty=1.1,
            )
        n_new = gen_ids.shape[1] - inputs.input_ids.shape[1]
        print(f"[QwenOCR] Generation: {time.time() - t_gen:.1f}s  "
              f"| new tokens: {n_new}")

        result = _processor.batch_decode(
            gen_ids[:, inputs.input_ids.shape[1]:],
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        )[0].strip()

        # Strip surrogate characters
        result = re.sub(r'[\ud800-\udfff]', '', result)
        return result

    except Exception as e:
        print(f"[QwenOCR] Inference error: {e}")
        return ""


def ocr_image_bytes(image_bytes: bytes, filename: Optional[str] = None,
                    max_tokens: int = 256) -> dict:
    """
    Run Qwen OCR on raw image bytes.

    Returns a result dict compatible with PDFExtractor's output format.
    """
    try:
        from PIL import Image
        import io
        image = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        return {
            'text': '',
            'method': 'qwen_ocr',
            'success': False,
            'error': f"Failed to open image: {e}",
            'ocr_engine': 'qwen2.5-vl',
        }

    t0 = time.time()
    text = ocr_image(image, max_tokens=max_tokens)
    elapsed = time.time() - t0

    return {
        'text': text if text else 'No text could be extracted from image',
        'method': 'qwen_ocr',
        'pages': 1,
        'success': bool(text),
        'error': None if text else 'Qwen OCR returned no text',
        'source': 'image',
        'ocr_used': True,
        'ocr_engine': 'qwen2.5-vl',
        'ocr_text_length': len(text),
        'text_length': len(text),
        'language': 'eng+ara',
        'filename': filename,
        'inference_time_seconds': round(elapsed, 2),
        'notes': f'Qwen2.5-VL OCR ({elapsed:.1f}s). Model: {MODEL_DIR}',
    }
