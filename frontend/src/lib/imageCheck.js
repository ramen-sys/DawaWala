// FR-4: check an image before upload. Type is judged by content (magic
// bytes), not by file name. The server repeats every check (SEC-07).
import { LIMITS } from "./limits.js";

export const OCR_FILE_PROBLEM = {
  type: "Choose a JPEG or PNG photo. This file is a different type.",
  size: `This photo is larger than ${LIMITS.MAX_IMAGE_MB} MB. Choose a smaller photo.`,
  small: `This photo is too small to read. Use one at least ${LIMITS.MIN_IMAGE_W} by ${LIMITS.MIN_IMAGE_H} pixels.`,
  empty: "This file is empty. Choose another photo.",
};

export function sniffImageType(bytes) {
  const b = Array.from(bytes.slice(0, 8));
  if (b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff) return "jpeg";
  if (b[0] === 0x89 && b[1] === 0x50 && b[2] === 0x4e && b[3] === 0x47) return "png";
  return null;
}

/** Returns an error message, or null when the file is acceptable. */
export async function checkImageFile(file, { measure = true } = {}) {
  if (!file || file.size === 0) return OCR_FILE_PROBLEM.empty;
  if (file.size > LIMITS.MAX_IMAGE_MB * 1_000_000) return OCR_FILE_PROBLEM.size;
  const head = new Uint8Array(await file.slice(0, 8).arrayBuffer());
  if (!sniffImageType(head)) return OCR_FILE_PROBLEM.type;
  if (measure && typeof createImageBitmap === "function") {
    try {
      const bmp = await createImageBitmap(file);
      const tooSmall = bmp.width < LIMITS.MIN_IMAGE_W || bmp.height < LIMITS.MIN_IMAGE_H;
      bmp.close?.();
      if (tooSmall) return OCR_FILE_PROBLEM.small;
    } catch {
      return OCR_FILE_PROBLEM.type;
    }
  }
  return null;
}
