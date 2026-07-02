"""Image preprocessing for Arabic OCR optimization.

This module is optional at runtime. If OpenCV or Pillow is unavailable,
we fall back to a simple byte-based placeholder so the OCR service can
still return a graceful empty result instead of crashing the pipeline.
"""

from typing import Optional, Tuple

try:
    import cv2  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - exercised in tests
    cv2 = None

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - exercised in tests
    np = None

try:
    from PIL import Image  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - exercised in tests
    Image = None


def preprocess_image(image_bytes: bytes, target_width: int = 800):
    """
    Full preprocessing pipeline for Arabic OCR
    
    Steps:
    1. Convert to grayscale
    2. Resize (maintain aspect ratio, target width)
    3. Increase contrast (CLAHE)
    4. Denoise
    5. Apply adaptive threshold
    
    Args:
        image_bytes: Raw image bytes
        target_width: Target width for resizing (important for Arabic)
    
    Returns:
        Preprocessed numpy array ready for OCR
    """
    if cv2 is None or np is None:
        return np.zeros((1, 1, 3), dtype=np.uint8) if np is not None else None

    # Convert bytes to numpy array
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if image is None:
        raise ValueError("Failed to decode image")
    
    # Step 1: Convert to grayscale
    gray = convert_to_grayscale(image)
    
    # Step 2: Resize (critical for Arabic text)
    resized = resize_for_arabic(gray, target_width=target_width)
    
    # Step 3: Increase contrast
    contrasted = enhance_contrast(resized)
    
    # Step 4: Denoise
    denoised = denoise_image(contrasted)
    
    # Step 5: Apply threshold
    thresholded = apply_threshold(denoised)
    
    return thresholded


def convert_to_grayscale(image):
    """Convert image to grayscale"""
    if cv2 is None:
        return image
    if len(image.shape) == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image


def resize_for_arabic(image, target_width: int = 800):
    """
    Resize image maintaining aspect ratio
    
    Very important for Arabic text recognition:
    - Too small: connected letters merge
    - Too large: increases processing time
    - 800px width is optimal for Arabic script
    """
    height, width = image.shape[:2]
    
    if width <= target_width:
        return image
    
    # Calculate new height maintaining aspect ratio
    ratio = target_width / width
    new_height = int(height * ratio)
    
    # Use INTER_CUBIC for upscaling, INTER_AREA for downscaling
    interpolation = cv2.INTER_AREA if ratio < 1 else cv2.INTER_CUBIC
    
    resized = cv2.resize(image, (target_width, new_height), interpolation=interpolation)
    return resized


def enhance_contrast(image):
    """
    Enhance contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization)
    
    This helps separate connected Arabic characters
    """
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(image)


def denoise_image(image):
    """Remove noise while preserving edges"""
    return cv2.fastNlMeansDenoising(image, None, 10, 7, 21)


def apply_threshold(image, method: str = "adaptive"):
    """
    Apply thresholding to create binary image
    
    Adaptive threshold works best for Arabic text with varying illumination
    """
    if method == "otsu":
        _, thresh = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    elif method == "adaptive":
        thresh = cv2.adaptiveThreshold(
            image, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 
            11, 2
        )
    else:
        _, thresh = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY)
    
    return thresh


def deskew_image(image):
    """
    Correct image skew/rotation
    
    Important for OCR accuracy
    """
    # Detect edges
    edges = cv2.Canny(image, 50, 150, apertureSize=3)
    
    # Find lines using Hough transform
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100, maxLineGap=10)
    
    if lines is None or len(lines) == 0:
        return image
    
    # Calculate average angle
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if x2 != x1:
            angle = np.arctan2(y2 - y1, x2 - x1) * 180.0 / np.pi
            angles.append(angle)
    
    if not angles:
        return image
    
    # Get median angle
    median_angle = np.median(angles)
    
    # Rotate image to correct skew
    if abs(median_angle) > 0.5:  # Only rotate if skew is significant
        height, width = image.shape[:2]
        center = (width // 2, height // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        rotated = cv2.warpAffine(
            image, rotation_matrix, (width, height),
            borderMode=cv2.BORDER_CONSTANT, borderValue=255
        )
        return rotated
    
    return image


def preprocess_for_display(image):
    """
    Preprocess image for visualization/debugging
    Returns RGB image
    """
    if len(image.shape) == 2:
        # Convert grayscale to RGB
        return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
