from app.ocr.engine import OCRLine,OCR_engine
import io
import shutil
from PIL import Image
import pytesseract
import os
import cv2
import numpy as np
import re
from rapidfuzz import fuzz

custom_path = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")

if os.path.exists(custom_path):
    pytesseract.pytesseract.tesseract_cmd = custom_path
elif shutil.which("tesseract"):
    # Found in system PATH (works automatically on Linux / Docker)
    pass

class Tesseract_engine(OCR_engine):
    def preprocess_image(self,image_bytes:bytes)->Image.Image:

        '''Contrast enhnancement step that makes stylized packing sharper'''
        #convertung bytes to open cv image
        np_arr=np.frombuffer(image_bytes,np.uint8)
        img=cv2.imdecode(np_arr,cv2.IMREAD_COLOR)
        #Convert to grayscale
        gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)


        # Contrast Stretching / CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        return Image.fromarray(enhanced)

    

   
    
    def _merge_data(self, data1: dict, data2: dict, similarity: int = 85) -> dict:
        KEYS = ["text", "conf", "block_num", "line_num", "left", "top", "width", "height"]
        
        merged = {key: list(data1[key]) for key in KEYS}  # copy, so data1 isn't changed

        for i in range(len(data2["text"])):
            text = data2["text"][i].strip()
            if not text:
                continue

            is_duplicate = any(
                abs(data2["left"][i] - merged["left"][j]) < 20
                and abs(data2["top"][i] - merged["top"][j]) < 20
                and fuzz.ratio(text.lower(), merged["text"][j].strip().lower()) >= similarity
                for j in range(len(merged["text"]))
            )

            if not is_duplicate:
                for key in KEYS:
                    merged[key].append(data2[key][i])

        return merged
    def extract_lines(self, image_bytes):
        #converting raw bytes to Pillow image and converting to grayscale

        image = self.preprocess_image(image_bytes)

        #converting image into ocr text
        custom_config = r'--psm 3'
        custom_config2 = r'--psm 6'
        
        data1=pytesseract.image_to_data(image=image,config=custom_config,output_type=pytesseract.Output.DICT)

        data2=pytesseract.image_to_data(image=image,config=custom_config2,output_type=pytesseract.Output.DICT)

        data=self._merge_data(data1,data2)
        MIN_CONFIDENCE=35.0#inore nois below 40 % confidence

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
            avg_conf=sum(w[1] for w in words_and_confs)/len(words_and_confs)
            if avg_conf<MIN_CONFIDENCE:
                continue
            line_text = " ".join(w[0] for w in words_and_confs).strip()
            clean_text = re.sub(r'^[^\w]+|[^\w]+$', '', line_text)
            if len(line_text) <= 2 and not any(char.isdigit() for char in line_text):
                continue
            ocr_lines.append(OCRLine(text=clean_text, confidence=round(avg_conf, 2)))

        return ocr_lines