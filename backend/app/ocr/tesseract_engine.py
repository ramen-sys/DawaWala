from app.ocr.engine import OCRLine,OCR_engine
import io
import shutil
from PIL import Image
import pytesseract
import os

custom_path = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")

if os.path.exists(custom_path):
    pytesseract.pytesseract.tesseract_cmd = custom_path
elif shutil.which("tesseract"):
    # Found in system PATH (works automatically on Linux / Docker)
    pass

class Tesseract_engine(OCR_engine):
    def extract_lines(self, image_bytes):
        #converting raw bytes to Pillow image and converting to grayscale

        image=Image.open(io.BytesIO(image_bytes))
        image=image.convert("L")

        #converting image into ocr text
        data=pytesseract.image_to_data(image=image,output_type=pytesseract.Output.DICT)

        lines_dict={}
        n_boxes=len(data["text"])
        for i in range(n_boxes):
            text=data["text"][i].strip()
            conf=float(data["conf"][i])

            if conf==-1 or not text:
                continue

            line_key=(data["block_num"][i],data["line_num"][i])
            if line_key not in lines_dict:
                lines_dict[line_key]=[]

            lines_dict[line_key].append((text,conf))

            ocr_lines = []
        for words_and_confs in lines_dict.values():
            line_text = " ".join(w[0] for w in words_and_confs)
            avg_conf = sum(w[1] for w in words_and_confs) / len(words_and_confs)
            ocr_lines.append(OCRLine(text=line_text, confidence=round(avg_conf, 2)))

        return ocr_lines