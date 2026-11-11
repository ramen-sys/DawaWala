import os
import re

import cv2
import numpy as np
import pytesseract
from PIL import Image

from app.ocr.engine import OCRLine, OCR_engine

custom_path = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")

if os.path.exists(custom_path):
    pytesseract.pytesseract.tesseract_cmd = custom_path

class Tesseract_engine(OCR_engine):
    def preprocess_image(self, image_bytes: bytes) -> Image.Image:
        image_array = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)

        longest_edge = max(enhanced.shape[:2])
        if longest_edge < 1200:
            scale = 1200 / longest_edge
            enhanced = cv2.resize(
                enhanced,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_CUBIC,
            )

        return Image.fromarray(enhanced)

    @staticmethod
    def _recognition_images(image: Image.Image) -> list[Image.Image]:
        gray = np.asarray(image)
        adaptive = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            11,
        )
        return [image, Image.fromarray(adaptive)]

    @staticmethod
    def _word_records(data: dict) -> list[dict]:
        records = []
        for index, raw_text in enumerate(data["text"]):
            text = raw_text.strip()
            confidence = float(data["conf"][index])
            if not text or confidence < 0:
                continue
            records.append({
                "text": text,
                "conf": confidence,
                "left": int(data["left"][index]),
                "top": int(data["top"][index]),
                "width": int(data["width"][index]),
                "height": int(data["height"][index]),
            })
        return records

    @staticmethod
    def _overlap_ratio(first: dict, second: dict) -> float:
        left = max(first["left"], second["left"])
        top = max(first["top"], second["top"])
        right = min(first["left"] + first["width"], second["left"] + second["width"])
        bottom = min(first["top"] + first["height"], second["top"] + second["height"])
        intersection = max(0, right - left) * max(0, bottom - top)
        smaller_area = min(
            first["width"] * first["height"],
            second["width"] * second["height"],
        )
        return intersection / smaller_area if smaller_area else 0

    @classmethod
    def _merge_data(cls, *data_sources: dict) -> list[dict]:
        """Merge OCR passes by word-box overlap, keeping the higher-confidence reading."""
        merged: list[dict] = []
        for source in data_sources:
            for candidate in cls._word_records(source):
                duplicate_index = next(
                    (
                        index
                        for index, existing in enumerate(merged)
                        if cls._overlap_ratio(candidate, existing) >= 0.5
                    ),
                    None,
                )
                if duplicate_index is None:
                    merged.append(candidate)
                elif candidate["conf"] > merged[duplicate_index]["conf"]:
                    merged[duplicate_index] = candidate
        return merged

    @staticmethod
    def _group_lines(words: list[dict]) -> list[list[dict]]:
        lines: list[list[dict]] = []
        for word in sorted(words, key=lambda value: (value["top"] + value["height"] / 2, value["left"])):
            center = word["top"] + word["height"] / 2
            target = next(
                (
                    line
                    for line in lines
                    if abs(
                        center
                        - sum(item["top"] + item["height"] / 2 for item in line) / len(line)
                    )
                    <= max(4, min(word["height"], max(item["height"] for item in line)) * 0.55)
                ),
                None,
            )
            if target is None:
                lines.append([word])
            else:
                target.append(word)
        return [sorted(line, key=lambda word: word["left"]) for line in lines]

    def extract_lines(self, image_bytes):
        image = self.preprocess_image(image_bytes)
        gray_image, adaptive_image = self._recognition_images(image)
        gray_data = pytesseract.image_to_data(
            gray_image,
            config="--oem 3 --psm 3",
            output_type=pytesseract.Output.DICT,
        )
        adaptive_data = pytesseract.image_to_data(
            adaptive_image,
            config="--oem 3 --psm 6",
            output_type=pytesseract.Output.DICT,
        )

        words = self._merge_data(gray_data, adaptive_data)
        lines = []
        for line_words in self._group_lines(words):
            line_text = " ".join(word["text"] for word in line_words)
            clean_text = re.sub(r"^[^\w]+|[^\w]+$", "", line_text)
            if not clean_text:
                continue
            confidence = sum(word["conf"] for word in line_words) / len(line_words)
            lines.append(OCRLine(text=clean_text, confidence=round(confidence, 2)))
        return lines