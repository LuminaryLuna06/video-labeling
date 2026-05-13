// frontend/src/app/core/services/dam.service.ts
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, from, throwError, forkJoin } from 'rxjs';
import { catchError, map, switchMap } from 'rxjs/operators';
import { SettingsService } from './settings.service';
import { composeRgba, composeRgbJpeg, padOrTrimFrames } from '../utils/rgba-compose';
import { SegmentationResponse } from '../models';

export interface DamHealthResponse {
  status: string;
  dam_loaded?: boolean;
  sam2_loaded?: boolean;
  dinov2_loaded?: boolean;
}

const DEFAULT_DAM_URL = 'http://localhost:8000';

@Injectable({ providedIn: 'root' })
export class DamService {
  constructor(
    private http: HttpClient,
    private settings: SettingsService
  ) {}

  private readonly VISUAL_PROMPT =
    '\nDescribe the masked region in detail. Focus on the visual appearance, ' +
    'shape, color, texture, and any distinguishing features of the object across the video frames.';

  private readonly CONTEXTUAL_PROMPT =
    '\nDescribe the overall scene in this video segment. Focus on the context, ' +
    'environment, spatial relationships between objects, and what is happening across the frames.';

  /**
   * Resolve the DAM base URL. Reads from SettingsService (which is backed by dedicated localStorage).
   * Falls back to DEFAULT_DAM_URL if blank.
   */
  private getDamUrl(): string {
    const url = (this.settings.getLocalDamUrl() || '').trim();
    return (url || DEFAULT_DAM_URL).replace(/\/+$/, '');
  }

  /**
   * Hit DAM /health directly from the browser. Replaces the backend
   * /api/settings/dam-url/test round-trip.
   */
  testConnection(url: string): Observable<{ status: 'ok' | 'error'; message: string; details?: DamHealthResponse }> {
    const target = url.trim().replace(/\/+$/, '');
    if (!target) {
      return throwError(() => ({ status: 'error' as const, message: 'URL is required' }));
    }
    return this.http.get<DamHealthResponse>(`${target}/health`).pipe(
      map((details) => ({
        status: 'ok' as const,
        message: `Connected to ${target}`,
        details
      })),
      catchError((err) => throwError(() => ({
        status: 'error' as const,
        message: this.formatError(target, err)
      })))
    );
  }

  /**
   * Run PySceneDetect on the DAM server to extract scenes and download them as a CSV file.
   */
  detectScenes(videoUrl: string, options?: { method?: string; threshold?: number; min_scene_len?: number }): Observable<{ scenes: any[] }> {
    const url = `${this.getDamUrl()}/scene-detect`;
    let absoluteVideoUrl = videoUrl;
    if (!absoluteVideoUrl.startsWith('http')) {
      absoluteVideoUrl = window.location.origin + absoluteVideoUrl;
    }
    
    return this.http.post<{ scenes: any[] }>(url, {
      video_url: absoluteVideoUrl,
      ...(options || {})
    }).pipe(
      catchError((err) => throwError(() => new Error(this.formatError(url, err))))
    );
  }

  /**
   * Send a brush mask + frame image to DAM's /segment endpoint (SAM2-backed).
   * Returns a refined object mask.
   */
  segmentObject(brushMask: string, frameImage?: string): Observable<SegmentationResponse> {
    const url = `${this.getDamUrl()}/segment`;
    return this.http.post<SegmentationResponse>(url, {
      brush_mask: brushMask,
      frame_image: frameImage ?? ''
    }).pipe(
      catchError((err) => throwError(() => new Error(this.formatError(url, err))))
    );
  }

  /**
   * Generate a visual or contextual caption for a region.
   * Mirrors backend /api/annotations/generate-caption.
   *
   * Visual: every frame gets the object mask as alpha.
   * Contextual: every frame gets a full-white mask (entire frame is the region).
   */
  generateCaption(
    frames: string[],
    maskImage: string,
    captionType: 'visual' | 'contextual'
  ): Observable<{ caption: string; caption_type: 'visual' | 'contextual' }> {
    if (!frames || frames.length === 0) {
      return throwError(() => new Error('frames is required'));
    }
    if (captionType === 'visual' && !maskImage) {
      return throwError(() => new Error('mask_image is required for visual caption'));
    }

    const padded = padOrTrimFrames(frames, 8);
    const maxSide = this.settings.getDamMaxImageSide();
    const composer =
      captionType === 'visual'
        ? (f: string) => composeRgba(f, maskImage, maxSide)
        : (f: string) => composeRgbJpeg(f, maxSide);
    const prompt = captionType === 'visual' ? this.VISUAL_PROMPT : this.CONTEXTUAL_PROMPT;

    return from(Promise.all(padded.map(composer))).pipe(
      switchMap((rgbaList) => this.callDamChat(rgbaList, prompt)),
      map((caption) => ({ caption, caption_type: captionType }))
    );
  }

  /**
   * Run visual + contextual caption generation in parallel.
   * Mirrors backend /api/annotations/generate-caption-batch.
   */
  generateCaptionBatch(
    frames: string[],
    maskImage: string
  ): Observable<{ visual_caption: string; contextual_caption: string; warnings?: string[] }> {
    const warnings: string[] = [];
    if (!maskImage) {
      warnings.push('mask_image was empty; visual caption skipped');
    }

    const visual$ = maskImage
      ? this.generateCaption(frames, maskImage, 'visual')
      : from(Promise.resolve({ caption: '', caption_type: 'visual' as const }));
    const contextual$ = this.generateCaption(frames, maskImage, 'contextual');

    return forkJoin({ visual: visual$, contextual: contextual$ }).pipe(
      map(({ visual, contextual }) => ({
        visual_caption: visual.caption,
        contextual_caption: contextual.caption,
        ...(warnings.length ? { warnings } : {})
      }))
    );
  }

  private callDamChat(rgbaImages: string[], prompt: string): Observable<string> {
    const url = `${this.getDamUrl()}/chat/completions`;
    const content: any[] = rgbaImages.map((rgba) => ({
      type: 'image_url',
      image_url: { url: rgba }
    }));
    content.push({ type: 'text', text: prompt });

    const payload = {
      model: 'describe_anything_model',
      messages: [{ role: 'user', content }],
      max_tokens: 512,
      temperature: 0.2,
      top_p: 0.5,
      use_cache: true,
      num_beams: 1
    };

    return this.http.post<any>(url, payload).pipe(
      map((res) => {
        const text = res?.choices?.[0]?.message?.content;
        if (typeof text !== 'string') {
          throw new Error('DAM returned an unexpected response shape');
        }
        return text;
      }),
      catchError((err) => throwError(() => new Error(this.formatError(url, err))))
    );
  }

  private formatError(target: string, err: any): string {
    if (err?.status === 0) {
      return `Cannot reach DAM at ${target}. Check the URL in Settings and that the server is running.`;
    }
    if (typeof err?.error === 'string') return err.error;
    if (err?.message) return err.message;
    return `DAM request failed (HTTP ${err?.status ?? '?'})`;
  }
}
