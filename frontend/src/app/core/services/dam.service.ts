// frontend/src/app/core/services/dam.service.ts
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { SettingsService } from './settings.service';
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

  /**
   * Resolve the DAM base URL. Reads from SettingsService (which is backed by localStorage).
   * Falls back to DEFAULT_DAM_URL if blank.
   */
  getDamUrl(): string {
    const url = (this.settings.get().dam_server_url || '').trim();
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

  private formatError(target: string, err: any): string {
    if (err?.status === 0) {
      return `Cannot reach DAM at ${target}. Check the URL in Settings and that the server is running.`;
    }
    if (typeof err?.error === 'string') return err.error;
    if (err?.message) return err.message;
    return `DAM request failed (HTTP ${err?.status ?? '?'})`;
  }
}
