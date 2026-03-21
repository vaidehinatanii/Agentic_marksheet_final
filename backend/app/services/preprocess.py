"""Image preprocessing service for OCR optimization."""
import io
import base64
import logging
from typing import Tuple, Optional
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import cv2
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def resize_image(image: Image.Image, max_dim: Optional[int] = None) -> Image.Image:
    """Resize image while maintaining aspect ratio."""
    if max_dim is None:
        max_dim = settings.max_image_dimension

    width, height = image.size
    if max(width, height) <= max_dim:
        return image

    if width > height:
        new_width = max_dim
        new_height = int(height * (max_dim / width))
    else:
        new_height = max_dim
        new_width = int(width * (max_dim / height))

    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)


def deskew_image(image: Image.Image) -> Image.Image:
    """Detect and correct image skew using Hough transform."""
    # Convert to OpenCV format
    img_array = np.array(image)
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array

    # Threshold to get binary image
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Find all white pixels
    coords = np.column_stack(np.where(binary > 0))
    if len(coords) < 10:
        return image  # Not enough points for deskew

    # Get minimum area rectangle
    angle = cv2.minAreaRect(coords)[-1]

    # Adjust angle
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    # If rotation is small, skip
    if abs(angle) < 0.5:
        return image

    # Rotate the image
    (h, w) = img_array.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(img_array, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    return Image.fromarray(rotated)


def enhance_image(image: Image.Image) -> Image.Image:
    """Enhance image contrast and sharpness for better OCR."""
    # Convert to numpy array for OpenCV processing
    img_array = np.array(image)

    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    if len(img_array.shape) == 3:
        # Convert to LAB color space
        lab = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)
        l_channel, a, b = cv2.split(lab)

        # Apply CLAHE to L channel
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l_channel = clahe.apply(l_channel)

        # Merge channels and convert back
        lab = cv2.merge([l_channel, a, b])
        img_array = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
        image = Image.fromarray(img_array)
    else:
        # Grayscale image
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        img_array = clahe.apply(img_array)
        image = Image.fromarray(img_array)

    # Increase contrast using PIL
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(1.5)

    # Increase sharpness
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(2.0)

    # Light denoise
    image = image.filter(ImageFilter.MedianFilter(size=3))

    # Apply slight sharpening filter
    image = image.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))

    return image


def binarize_image(image: Image.Image) -> Image.Image:
    """Convert image to high-contrast black and white."""
    img_array = np.array(image)

    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array

    # Adaptive thresholding
    binary = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31, 10
    )

    return Image.fromarray(binary)


def preprocess_image(image_bytes: bytes) -> bytes:
    """
    Complete preprocessing pipeline with multiple enhancements.
    Returns processed image as bytes.
    """
    try:
        # Load image
        image = Image.open(io.BytesIO(image_bytes))

        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Resize if too large (but keep high quality)
        image = resize_image(image)

        # Try deskew
        try:
            image = deskew_image(image)
        except Exception:
            pass  # Continue if deskew fails

        # Enhance with CLAHE, contrast, sharpness
        image = enhance_image(image)

        # Convert back to bytes with high quality
        output = io.BytesIO()
        image.save(output, format='PNG', optimize=True, quality=100)
        return output.getvalue()

    except Exception as e:
        logger.warning("Image preprocessing failed, returning original: %s", e)
        return image_bytes


def image_to_base64(image_bytes: bytes) -> str:
    """Convert image bytes to base64 data URL."""
    base64_str = base64.b64encode(image_bytes).decode('utf-8')
    return f"data:image/png;base64,{base64_str}"


def pdf_to_image(pdf_bytes: bytes, dpi: Optional[int] = None) -> bytes:
    """
    Convert first page of PDF to image at high DPI.
    Returns image bytes.
    """
    if dpi is None:
        dpi = settings.pdf_render_dpi

    import fitz  # PyMuPDF

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    if len(doc) == 0:
        raise ValueError("PDF has no pages")

    # Render first page at higher DPI for better OCR
    page = doc[0]
    pix = page.get_pixmap(dpi=dpi, alpha=False)

    # Convert to PIL Image
    img_data = pix.tobytes("png")
    doc.close()

    return img_data


async def process_file_to_image(file_data: bytes, filename: str) -> Tuple[bytes, str]:
    """
    Process uploaded file to image bytes.
    Returns (image_bytes, mime_type).
    """
    filename_lower = filename.lower()

    if filename_lower.endswith('.pdf'):
        image_bytes = pdf_to_image(file_data)
        return image_bytes, "image/png"
    elif filename_lower.endswith(('.jpg', '.jpeg')):
        return file_data, "image/jpeg"
    elif filename_lower.endswith('.png'):
        return file_data, "image/png"
    else:
        # Try to process as image
        try:
            image = Image.open(io.BytesIO(file_data))
            if image.mode != 'RGB':
                image = image.convert('RGB')
            output = io.BytesIO()
            image.save(output, format='PNG')
            return output.getvalue(), "image/png"
        except Exception:
            raise ValueError(f"Unsupported file type: {filename}")
