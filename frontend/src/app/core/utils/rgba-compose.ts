/**
 * Load a base64 image data URL (or raw base64 PNG/JPEG) into an HTMLImageElement.
 * Accepts both "data:image/png;base64,xxx" and raw "xxx" forms.
 */
function loadImage(b64: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('Failed to load image from base64 data'));
    img.src = b64.startsWith('data:') ? b64 : `data:image/png;base64,${b64}`;
  });
}

/**
 * Scale (w, h) so the SHORT edge equals `target`, preserving aspect ratio.
 * Never upscales: if the short edge is already smaller than the target, the
 * image is returned as-is. This ensures the image stays at least as large as
 * DAM's 384x384 input on both dimensions when target >= 384.
 */
function fitToShortEdge(w: number, h: number, target: number): { w: number; h: number } {
  const shortest = Math.min(w, h);
  if (shortest <= target) return { w, h };
  const scale = target / shortest;
  return { w: Math.round(w * scale), h: Math.round(h * scale) };
}

/**
 * Compose an RGBA PNG where alpha = mask grayscale.
 * Port of backend `_make_rgba_image` (PIL → Canvas).
 * Mask is resized to frame size with nearest-neighbor to match PIL's Image.NEAREST.
 *
 * Browser-drawn masks are grayscale PNGs (R = G = B); we read the R channel as alpha,
 * which matches PIL's `.convert('L')` luminance on grayscale input.
 */
export async function composeRgba(
  frameB64: string,
  maskB64: string,
  maxSide?: number | null
): Promise<string> {
  const [frame, mask] = await Promise.all([loadImage(frameB64), loadImage(maskB64)]);

  const { w, h } = maxSide && maxSide > 0
    ? fitToShortEdge(frame.naturalWidth, frame.naturalHeight, maxSide)
    : { w: frame.naturalWidth, h: frame.naturalHeight };

  const frameCanvas = document.createElement('canvas');
  frameCanvas.width = w;
  frameCanvas.height = h;
  const frameCtx = frameCanvas.getContext('2d');
  if (!frameCtx) throw new Error('Canvas 2D context unavailable');
  frameCtx.drawImage(frame, 0, 0, w, h);
  const frameData = frameCtx.getImageData(0, 0, w, h);

  const maskCanvas = document.createElement('canvas');
  maskCanvas.width = w;
  maskCanvas.height = h;
  const maskCtx = maskCanvas.getContext('2d');
  if (!maskCtx) throw new Error('Canvas 2D context unavailable');
  maskCtx.imageSmoothingEnabled = false; // mimic PIL Image.NEAREST — keep mask edge crisp
  maskCtx.drawImage(mask, 0, 0, w, h);
  const maskData = maskCtx.getImageData(0, 0, w, h);

  // Overwrite alpha channel with mask R channel.
  const pixels = frameData.data;
  const maskPixels = maskData.data;
  for (let i = 0; i < pixels.length; i += 4) {
    pixels[i + 3] = maskPixels[i];
  }
  frameCtx.putImageData(frameData, 0, 0);

  return frameCanvas.toDataURL('image/png');
}

/**
 * Compose an RGBA PNG with alpha = 255 everywhere (entire frame visible).
 * Port of backend `_make_full_mask_rgba`. Used for contextual captions.
 */
export async function composeFullMaskRgba(
  frameB64: string,
  maxSide?: number | null
): Promise<string> {
  const frame = await loadImage(frameB64);
  const { w, h } = maxSide && maxSide > 0
    ? fitToShortEdge(frame.naturalWidth, frame.naturalHeight, maxSide)
    : { w: frame.naturalWidth, h: frame.naturalHeight };

  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Canvas 2D context unavailable');
  ctx.drawImage(frame, 0, 0, w, h);
  // drawImage already produces alpha=255 for opaque sources; this is explicit and safe.
  const data = ctx.getImageData(0, 0, w, h);
  for (let i = 3; i < data.data.length; i += 4) {
    data.data[i] = 255;
  }
  ctx.putImageData(data, 0, 0);

  return canvas.toDataURL('image/png');
}

/**
 * Ensure exactly `target` frames by evenly sampling (if more) or padding the last frame (if fewer).
 * Port of backend `_pad_or_trim_frames`.
 */
export function padOrTrimFrames<T>(frames: T[], target = 8): T[] {
  if (frames.length === 0) return [];
  if (frames.length >= target) {
    const step = frames.length / target;
    const out: T[] = [];
    for (let i = 0; i < target; i++) {
      out.push(frames[Math.floor(i * step)]);
    }
    return out;
  }
  const out = [...frames];
  while (out.length < target) {
    out.push(out[out.length - 1]);
  }
  return out;
}
