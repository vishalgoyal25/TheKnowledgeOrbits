/**
 * @file cloudinary-loader.ts
 * @description Custom Next.js image loader (V2 — Vercel quota fix).
 *
 * WHY: hero images are already optimized by Cloudinary at UPLOAD time
 * (backend image_service.py: fetch_format="auto", quality="auto:good",
 * width=1200, crop="limit"). Letting Vercel re-optimize them a second time
 * burned the free-tier "Image Optimization Transformations" quota AND routed
 * the bytes through Vercel origin (Fast Origin Transfer). This loader hands
 * responsive resizing to Cloudinary's own CDN instead:
 *
 *   - Cloudinary URLs → inject `f_auto,q_auto,w_<width>` after `/upload/`, so
 *     Cloudinary serves a per-viewport-sized, format-optimized image directly.
 *     Vercel's optimizer is bypassed → 0 transformations, 0 origin transfer.
 *   - Any other URL (Wikipedia fallback thumbnails, local /public assets) is
 *     returned unchanged — already small, served as-is.
 *
 * Setting `images.loader = "custom"` in next.config.ts applies this globally,
 * so NO Vercel image optimization runs for any <Image> in the app. Responsive
 * `srcset` still works because Next.js calls this loader once per width.
 */

interface CloudinaryLoaderArgs {
  src: string;
  width: number;
  quality?: number;
}

export default function cloudinaryLoader({
  src,
  width,
  quality,
}: CloudinaryLoaderArgs): string {
  // Only rewrite Cloudinary delivery URLs; pass everything else through.
  if (!src.includes("res.cloudinary.com") || !src.includes("/upload/")) {
    return src;
  }

  // f_auto = best format per browser, q_auto (or the requested quality),
  // w_<width> = responsive size, c_limit = never upscale past the source.
  const transforms = `f_auto,q_${quality ?? "auto"},w_${width},c_limit`;

  // Insert the transformation segment immediately after `/upload/`.
  return src.replace("/upload/", `/upload/${transforms}/`);
}
