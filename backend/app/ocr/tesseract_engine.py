from app.ocr.engine import OCRLine,OCR_engine
import io
from PIL import Image
import pytesseract

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

            line_key=[data["block_num"][i],data["line_num"][i]]
            if line_key not in lines_dict:
                lines_dict[line_key]=[]

            lines_dict[line_key].append((text,conf))