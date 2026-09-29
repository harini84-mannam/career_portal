# opencv helpes functions to clean scanned resume images before ocr
# tesseract works much better on a clean, high-contrast image than a raw scan 

import cv2
import numpy as np


def to_grayscale(img: np.ndarray) -> np.ndarray:
    # converts the image into grayscale, skips if its already a grayscale image
    if len(img.shape) == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def remove_noise(img: np.ndarray) -> np.ndarray:
# removes small speckle noise with a median blur, then run a stronger and removes noises to clean the grainy scans from old documents or images
    denoised = cv2.medianBlur(img, 3)
    denoised = cv2.fastNlMeansDenoising(denoised, h=10, templateWindowSize=7, searchWindowSize=21)
    return denoised


def sharpen(img: np.ndarray) -> np.ndarray:
# applies  a simple sharpening filter to make text edges clearer
    kernel = np.array([[0, -1, 0],
                        [-1, 5, -1],
                        [0, -1, 0]])
    return cv2.filter2D(img, -1, kernel)


def adaptive_threshold(img: np.ndarray) -> np.ndarray:
# coverts the image to pure black and white using adaptive thresholding 
    return cv2.adaptiveThreshold(
        img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )


def deskew(img: np.ndarray) -> np.ndarray:
    # fixes tilted scans. finds the angle of the text block using minAreaRect and rotates the image back straight
    # if its already straight it ignores 
    inverted = cv2.bitwise_not(img)
    coords = np.column_stack(np.where(inverted > 0))
    if coords.shape[0] < 20:
        return img 
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.1:
        return img  
    (h, w) = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    return rotated


def enhance_contrast(img: np.ndarray) -> np.ndarray:
# improve local contrast using CLAHE
# helps make faint text eaiser  for OCR to recognize
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    return clahe.apply(img)


def remove_borders(img: np.ndarray) -> np.ndarray:
# remove black scanner borders by cropping to the document content
# skip the crop if the detected area looks too small
    _, thresh = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return img
    x, y, w, h = cv2.boundingRect(np.vstack(contours))
    pad = 5
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(img.shape[1], x + w + pad), min(img.shape[0], y + h + pad)
    if (x1 - x0) < 20 or (y1 - y0) < 20:
        return img  
    return img[y0:y1, x0:x1]


def enhance_resolution(img: np.ndarray, scale: float = 1.5) -> np.ndarray:
# upscale small or low-resolution images to improve OCR accuracy
# skip images that are already large enough
    h, w = img.shape[:2]
    if max(h, w) >= 2000:
        return img
    return cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)


def preprocess_pipeline(img: np.ndarray) -> np.ndarray:
# runs the complete preprocessing pipeline
# the final output is a cleaned binary image ready for tesseract OCR
    gray = to_grayscale(img)
    gray = enhance_resolution(gray)
    gray = remove_noise(gray)
    gray = sharpen(gray)
    gray = enhance_contrast(gray)
    gray = deskew(gray)
    gray = remove_borders(gray)
    binary = adaptive_threshold(gray)
    return binary


def load_image_from_bytes(data: bytes) -> np.ndarray:
# decode uploaded image bytes into an OpenCV image
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img
