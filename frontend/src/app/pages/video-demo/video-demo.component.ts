import { CommonModule } from '@angular/common';
import { Component, ElementRef, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { VideoService } from '../../core/services/video.service';
import { ImageService } from '../../core/services/image.service';
import { ProjectService } from '../../core/services/project.service';
import { Project } from '../../core/models';
import { SimilarImageMatch } from '../../core/services/video.service';

@Component({
  selector: 'app-video-demo',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatFormFieldModule,
    MatSelectModule,
  ],
  templateUrl: './video-demo.component.html',
  styleUrls: ['./video-demo.component.scss']
})
export class VideoDemoComponent implements OnInit, OnDestroy {
  @ViewChild('demoVideo') demoVideoRef?: ElementRef<HTMLVideoElement>;

  selectedFile: File | null = null;
  videoUrl: string | null = null;
  fileName = '';
  prompt = 'Describe this video in detail, including all visible objects, actions, and scenes.';
  processing = false;
  finalDescription = '';
  englishDescription = '';
  vietnameseDescription = '';
  damDescription = '';
  similarImages: SimilarImageMatch[] = [];
  similarImagesMessage = '';
  retrievalDebugText = '';
  hasGenerated = false;
  projects: Project[] = [];
  selectedProjectId = '';
  indexing = false;
  indexSummary = '';
  speaking = false;
  autoNarrationEnabled = true;
  private narrationCancelled = false;

  constructor(
    private videoService: VideoService,
    private imageService: ImageService,
    private projectService: ProjectService,
    private snackBar: MatSnackBar,
  ) {}

  ngOnInit(): void {
    this.projectService.getProjects().subscribe({
      next: (projects) => {
        this.projects = projects || [];
      },
      error: () => {
        this.snackBar.open('Failed to load projects', 'Close', { duration: 3000, panelClass: 'snack-error' });
      }
    });
  }

  onVideoSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    this.stopNarration(false);
    this.selectedFile = file;
    this.clearVideoUrl();
    this.videoUrl = URL.createObjectURL(file);
    this.fileName = file.name;
    this.finalDescription = '';
    this.englishDescription = '';
    this.vietnameseDescription = '';
    this.damDescription = '';
    this.similarImages = [];
    this.similarImagesMessage = '';
    this.retrievalDebugText = '';
    this.hasGenerated = false;
  }

  generateDescription(): void {
    if (!this.selectedFile || this.processing) return;

    this.processing = true;
    this.finalDescription = '';
    this.englishDescription = '';
    this.vietnameseDescription = '';
    this.similarImages = [];
    this.similarImagesMessage = '';
    this.retrievalDebugText = '';
    this.hasGenerated = false;

    this.videoService.processVideoDemo(this.selectedFile, {
      num_frames: 16,
      prompt: this.prompt,
      use_gemini: true,
    }).subscribe({
      next: (res) => {
        this.processing = false;
        this.damDescription = res.dam_description || '';
        this.englishDescription = res.english_description || '';
        this.vietnameseDescription = res.vietnamese_description || '';
        this.finalDescription = res.final_description || res.gemini_description || res.dam_description || '';
        this.similarImages = res.similar_images || [];
        this.similarImagesMessage = res.similar_images_message || '';
        const dbg = res.retrieval_debug;
        this.retrievalDebugText = dbg
          ? `Debug: image vectors=${dbg.image_embedding_count}, kb vectors=${dbg.kb_embedding_count}, similar hits=${dbg.similar_images_count}, kb hits=${dbg.knowledge_hits_count}`
          : '';
        this.hasGenerated = true;
        if (!this.finalDescription) {
          this.snackBar.open('No description generated', 'Close', { duration: 3000 });
          return;
        }

        if (this.autoNarrationEnabled) {
          this.playNarrationWithVideo();
        }
      },
      error: (err) => {
        this.processing = false;
        const msg = err?.error?.error || 'Failed to process video';
        this.snackBar.open(msg, 'Close', { duration: 4000, panelClass: 'snack-error' });
      }
    });
  }

  playNarrationWithVideo(): void {
    const narrationText = this.getNarrationText();
    if (!narrationText) {
      this.snackBar.open('No caption available for narration', 'Close', { duration: 2500 });
      return;
    }

    const synth = window.speechSynthesis;
    if (!synth || typeof SpeechSynthesisUtterance === 'undefined') {
      this.snackBar.open('Text-to-speech is not supported in this browser', 'Close', { duration: 3500, panelClass: 'snack-error' });
      return;
    }

    this.stopNarration(false);
    this.narrationCancelled = false;
    this.speaking = true;

    const video = this.demoVideoRef?.nativeElement;
    if (video) {
      video.currentTime = 0;
      video.play().catch(() => {
        this.snackBar.open('Video autoplay was blocked. Press play to start the video.', 'Close', { duration: 3500 });
      });
    }

    const chunks = this.chunkNarrationText(narrationText);
    this.speakChunks(chunks, this.getNarrationLanguage(narrationText));
  }

  stopNarration(alsoPauseVideo = true): void {
    this.narrationCancelled = true;
    this.speaking = false;
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }

    if (alsoPauseVideo) {
      this.demoVideoRef?.nativeElement.pause();
    }
  }

  private getNarrationText(): string {
    return (
      this.vietnameseDescription?.trim() ||
      this.englishDescription?.trim() ||
      this.finalDescription?.trim() ||
      ''
    );
  }

  private getNarrationLanguage(text: string): string {
    return /[\u00C0-\u1EF9]/.test(text) ? 'vi-VN' : 'en-US';
  }

  private chunkNarrationText(text: string, maxLength = 220): string[] {
    const normalized = text.replace(/\s+/g, ' ').trim();
    if (!normalized) return [];

    const sentences = normalized.match(/[^.!?]+[.!?]?/g) || [normalized];
    const chunks: string[] = [];
    let current = '';

    for (const sentence of sentences) {
      const part = sentence.trim();
      if (!part) continue;

      if (!current) {
        current = part;
        continue;
      }

      if (`${current} ${part}`.length <= maxLength) {
        current = `${current} ${part}`;
      } else {
        chunks.push(current);
        current = part;
      }
    }

    if (current) {
      chunks.push(current);
    }

    return chunks;
  }

  private speakChunks(chunks: string[], lang: string, index = 0): void {
    if (this.narrationCancelled || index >= chunks.length) {
      this.speaking = false;
      return;
    }

    const utterance = new SpeechSynthesisUtterance(chunks[index]);
    utterance.lang = lang;
    utterance.rate = lang === 'vi-VN' ? 0.95 : 1;
    utterance.pitch = 1;

    const voices = window.speechSynthesis.getVoices() || [];
    const matchingVoice = voices.find((voice) => voice.lang.toLowerCase().startsWith(lang.toLowerCase().split('-')[0]));
    if (matchingVoice) {
      utterance.voice = matchingVoice;
    }

    utterance.onend = () => {
      this.speakChunks(chunks, lang, index + 1);
    };

    utterance.onerror = () => {
      this.speaking = false;
      this.snackBar.open('Text-to-speech playback failed', 'Close', { duration: 3000, panelClass: 'snack-error' });
    };

    window.speechSynthesis.speak(utterance);
  }

  autoIndexProjectImages(): void {
    if (!this.selectedProjectId || this.indexing) return;

    this.indexing = true;
    this.indexSummary = '';

    this.imageService.getProjectImages(this.selectedProjectId).subscribe({
      next: (images) => {
        const imageIds = (images || []).map((img) => img.id).filter((id) => !!id);
        if (!imageIds.length) {
          this.indexing = false;
          this.indexSummary = 'No images found in selected project.';
          this.snackBar.open(this.indexSummary, 'Close', { duration: 3000 });
          return;
        }

        this.imageService.indexImagesBatch(imageIds).subscribe({
          next: (res) => {
            this.indexing = false;
            const total = res?.total ?? imageIds.length;
            const success = res?.success_count ?? 0;
            const failed = Math.max(0, total - success);
            this.indexSummary = `Indexed ${success}/${total} images${failed ? `, failed: ${failed}` : ''}.`;
            this.snackBar.open(this.indexSummary, 'Close', { duration: 3500 });
          },
          error: (err) => {
            this.indexing = false;
            const msg = err?.error?.error || 'Batch indexing failed';
            this.indexSummary = msg;
            this.snackBar.open(msg, 'Close', { duration: 4000, panelClass: 'snack-error' });
          }
        });
      },
      error: (err) => {
        this.indexing = false;
        const msg = err?.error?.error || 'Failed to fetch project images';
        this.indexSummary = msg;
        this.snackBar.open(msg, 'Close', { duration: 4000, panelClass: 'snack-error' });
      }
    });
  }

  private clearVideoUrl(): void {
    if (this.videoUrl) {
      URL.revokeObjectURL(this.videoUrl);
      this.videoUrl = null;
    }
  }

  ngOnDestroy(): void {
    this.stopNarration(false);
    this.clearVideoUrl();
  }
}
