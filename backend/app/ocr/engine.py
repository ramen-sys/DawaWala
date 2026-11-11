from abc import ABC, abstractmethod
from pydantic import BaseModel

class OCRLine(BaseModel):
    text:str
    confidence:float

class OCR_engine(ABC):
    @abstractmethod
    def extract_lines(self,image_bytes:bytes)->list[OCRLine]:
        """Extract text lines and confidence score from raw image bytes"""
        pass
