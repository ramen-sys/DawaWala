from app.ocr.tesseract_engine import Tesseract_engine
import sys
from pathlib import Path
# Ensure backend directory is in python path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.append(str(backend_dir))
def test_engine():
    engine=Tesseract_engine()
   

    image_path = backend_dir / "samples" / "medical_sample.jpg"
    
    if not image_path.exists():
        print(f"Error: Could not find image at {image_path}")
        print("Please check that your image is saved inside the backend/samples directory!")
        return

    with open (image_path,"rb") as f:
        image_bytes=f.read()

    ocr_lines=engine.extract_lines(image_bytes)

    for line in ocr_lines:
        print("line: ",line)

if __name__ == "__main__":
    test_engine()