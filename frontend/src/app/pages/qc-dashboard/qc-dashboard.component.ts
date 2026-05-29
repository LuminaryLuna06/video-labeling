import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatMenuModule } from '@angular/material/menu';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatTableModule } from '@angular/material/table';
import { MatTabsModule } from '@angular/material/tabs';
import { MatBadgeModule } from '@angular/material/badge';
import { HttpClient } from '@angular/common/http';
import { AuthService } from '../../core/services/auth.service';
import { SettingsService } from '../../core/services/settings.service';
import { SettingsDialogComponent } from '../settings-dialog/settings-dialog.component';

interface VideoStatusCounts {
  not_submitted: number;
  pending_review: number;
  in_review: number;
  approved: number;
  rejected: number;
}

interface QCStats {
  total_videos: number;
  by_status: VideoStatusCounts;
  by_project: { [key: string]: VideoStatusCounts & { total: number } };
  by_user: UserStats[];
  recent_reviews: ReviewItem[];
  pending_reviews: PendingReviewItem[];
}

interface ImageQCStats {
  total_images: number;
  by_status: {
    pending: number;
    approved: number;
    rejected: number;
    in_review: number;
  };
  by_project: { [key: string]: { total: number; approved: number; rejected: number; pending: number; in_review: number } };
  by_user: UserStats[];
  recent_reviews: ImageReviewItem[];
  pending_reviews: ImagePendingReviewItem[];
}

interface UserStats {
  id: string;
  name: string;
  color: string;
  total_reviews: number;
  approved: number;
  rejected: number;
}

interface ReviewItem {
  video_id: string;
  video_name: string;
  project_name: string;
  reviewer_name: string;
  reviewer_color: string;
  status: string;
  reviewed_at: string;
}

interface ImageReviewItem {
  image_id: string;
  image_name: string;
  project_name: string;
  reviewer_name: string;
  reviewer_color: string;
  status: string;
  reviewed_at: string;
}

interface PendingReviewItem {
  video_id: string;
  video_name: string;
  project_name: string;
  subpart_name: string;
  pending_reviewers: { id: string; name: string; color: string }[];
  created_at: string;
}

interface ImagePendingReviewItem {
  image_id: string;
  image_name: string;
  project_name: string;
  subpart_name: string;
  pending_reviewers: { id: string; name: string; color: string }[];
  created_at: string;
}

@Component({
  selector: 'app-qc-dashboard',
  standalone: true,
  imports: [
    CommonModule, RouterModule,
    MatToolbarModule, MatButtonModule, MatIconModule, MatCardModule,
    MatChipsModule, MatMenuModule, MatDialogModule, MatProgressSpinnerModule,
    MatTooltipModule, MatTableModule, MatTabsModule, MatBadgeModule
  ],
  templateUrl: './qc-dashboard.component.html',
  styleUrls: ['./qc-dashboard.component.scss']
})
export class QcDashboardComponent implements OnInit {
  loading = true;
  loadingImages = true;
  stats: QCStats | null = null;
  imageStats: ImageQCStats | null = null;
  user = this.authService.user;

  // Tab selection: 'video' | 'image'
  activeTab: 'video' | 'image' = 'video';

  displayedReviewColumns = ['video', 'project', 'reviewer', 'status', 'date', 'actions'];
  displayedPendingColumns = ['video', 'project', 'subpart', 'pending_reviewers', 'waiting_since', 'actions'];

  // Pagination for pending reviews (video)
  pendingPage = 1;
  pendingPageSize = 10;

  // Pagination for recent activity (video)
  activityPage = 1;
  activityPageSize = 10;

  // Pagination for pending reviews (image)
  imagePendingPage = 1;
  imagePendingPageSize = 10;

  // Pagination for recent activity (image)
  imageActivityPage = 1;
  imageActivityPageSize = 10;

  constructor(
    private http: HttpClient,
    private authService: AuthService,
    private settingsService: SettingsService,
    private router: Router,
    private dialog: MatDialog
  ) {}

  ngOnInit(): void {
    this.loadStats();
    this.loadImageStats();
  }

  loadStats(): void {
    this.loading = true;
    this.http.get<QCStats>('/api/videos/qc-stats').subscribe({
      next: (data) => {
        this.stats = data;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      }
    });
  }

  loadImageStats(): void {
    this.loadingImages = true;
    this.http.get<ImageQCStats>('/api/images/qc-stats').subscribe({
      next: (data) => {
        this.imageStats = data;
        this.loadingImages = false;
      },
      error: () => {
        this.loadingImages = false;
      }
    });
  }

  refreshAll(): void {
    this.loadStats();
    this.loadImageStats();
  }

  get projectStats(): {
    name: string;
    total: number;
    not_submitted: number;
    pending_review: number;
    in_review: number;
    approved: number;
    rejected: number;
    approvalRate: number;
  }[] {
    if (!this.stats) return [];
    return Object.entries(this.stats.by_project).map(([name, data]) => {
      const decided = data.approved + data.rejected;
      return {
        name,
        ...data,
        approvalRate: decided > 0 ? Math.round((data.approved / decided) * 100) : 0
      };
    }).sort((a, b) => b.total - a.total);
  }

  /** Rate over items that already have a final decision (approved + rejected). */
  get approvalRate(): number {
    if (!this.stats) return 0;
    const decided = this.stats.by_status.approved + this.stats.by_status.rejected;
    return decided > 0 ? Math.round((this.stats.by_status.approved / decided) * 100) : 0;
  }

  get rejectionRate(): number {
    if (!this.stats) return 0;
    const decided = this.stats.by_status.approved + this.stats.by_status.rejected;
    return decided > 0 ? Math.round((this.stats.by_status.rejected / decided) * 100) : 0;
  }

  // Image Stats
  get imageProjectStats(): { name: string; total: number; approved: number; rejected: number; pending: number; in_review: number; approvalRate: number }[] {
    if (!this.imageStats) return [];
    return Object.entries(this.imageStats.by_project).map(([name, data]) => ({
      name,
      ...data,
      approvalRate: data.total > 0 ? Math.round((data.approved / data.total) * 100) : 0
    })).sort((a, b) => b.total - a.total);
  }

  get imageApprovalRate(): number {
    if (!this.imageStats || this.imageStats.total_images === 0) return 0;
    return Math.round((this.imageStats.by_status.approved / this.imageStats.total_images) * 100);
  }

  get imageRejectionRate(): number {
    if (!this.imageStats || this.imageStats.total_images === 0) return 0;
    return Math.round((this.imageStats.by_status.rejected / this.imageStats.total_images) * 100);
  }

  // Pagination: Pending Reviews
  get paginatedPendingReviews(): PendingReviewItem[] {
    if (!this.stats) return [];
    const start = (this.pendingPage - 1) * this.pendingPageSize;
    return this.stats.pending_reviews.slice(start, start + this.pendingPageSize);
  }

  get pendingTotalPages(): number {
    if (!this.stats) return 1;
    return Math.ceil(this.stats.pending_reviews.length / this.pendingPageSize) || 1;
  }

  pendingPrevPage(): void {
    if (this.pendingPage > 1) this.pendingPage--;
  }

  pendingNextPage(): void {
    if (this.pendingPage < this.pendingTotalPages) this.pendingPage++;
  }

  // Pagination: Recent Activity
  get paginatedRecentReviews(): ReviewItem[] {
    if (!this.stats) return [];
    const start = (this.activityPage - 1) * this.activityPageSize;
    return this.stats.recent_reviews.slice(start, start + this.activityPageSize);
  }

  get activityTotalPages(): number {
    if (!this.stats) return 1;
    return Math.ceil(this.stats.recent_reviews.length / this.activityPageSize) || 1;
  }

  activityPrevPage(): void {
    if (this.activityPage > 1) this.activityPage--;
  }

  activityNextPage(): void {
    if (this.activityPage < this.activityTotalPages) this.activityPage++;
  }

  // Pagination: Image Pending Reviews
  get paginatedImagePendingReviews(): ImagePendingReviewItem[] {
    if (!this.imageStats) return [];
    const start = (this.imagePendingPage - 1) * this.imagePendingPageSize;
    return this.imageStats.pending_reviews.slice(start, start + this.imagePendingPageSize);
  }

  get imagePendingTotalPages(): number {
    if (!this.imageStats) return 1;
    return Math.ceil(this.imageStats.pending_reviews.length / this.imagePendingPageSize) || 1;
  }

  imagePendingPrevPage(): void {
    if (this.imagePendingPage > 1) this.imagePendingPage--;
  }

  imagePendingNextPage(): void {
    if (this.imagePendingPage < this.imagePendingTotalPages) this.imagePendingPage++;
  }

  // Pagination: Image Recent Activity
  get paginatedImageRecentReviews(): ImageReviewItem[] {
    if (!this.imageStats) return [];
    const start = (this.imageActivityPage - 1) * this.imageActivityPageSize;
    return this.imageStats.recent_reviews.slice(start, start + this.imageActivityPageSize);
  }

  get imageActivityTotalPages(): number {
    if (!this.imageStats) return 1;
    return Math.ceil(this.imageStats.recent_reviews.length / this.imageActivityPageSize) || 1;
  }

  imageActivityPrevPage(): void {
    if (this.imageActivityPage > 1) this.imageActivityPage--;
  }

  imageActivityNextPage(): void {
    if (this.imageActivityPage < this.imageActivityTotalPages) this.imageActivityPage++;
  }

  openVideo(videoId: string): void {
    this.router.navigate(['/editor', videoId]);
  }

  openImage(imageId: string): void {
    this.router.navigate(['/image-editor', imageId]);
  }

  getStatusClass(status: string): string {
    switch (status) {
      case 'approved': 
      case 'approve': return 'status-approved';
      case 'rejected':
      case 'reject': return 'status-rejected';
      case 'in_review': return 'status-in-review';
      default: return 'status-pending';
    }
  }

  getStatusIcon(status: string): string {
    switch (status) {
      case 'approved':
      case 'approve': return 'check_circle';
      case 'rejected':
      case 'reject': return 'cancel';
      case 'in_review': return 'pending';
      default: return 'schedule';
    }
  }

  /** Parse date string from backend (UTC) properly */
  private parseUtcDate(dateStr: string): Date {
    // Backend returns ISO format in UTC, ensure we parse it correctly
    if (!dateStr) return new Date();
    // If string doesn't end with Z or timezone offset, append Z to indicate UTC
    if (!dateStr.endsWith('Z') && !dateStr.match(/[+-]\d{2}:\d{2}$/)) {
      dateStr = dateStr + 'Z';
    }
    return new Date(dateStr);
  }

  formatDate(dateStr: string): string {
    if (!dateStr) return '-';
    const date = this.parseUtcDate(dateStr);
    const timezone = this.settingsService.get().timezone || 'Asia/Ho_Chi_Minh';
    
    // Get current time
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    
    if (days === 0) {
      const hours = Math.floor(diff / (1000 * 60 * 60));
      if (hours === 0) {
        const minutes = Math.floor(diff / (1000 * 60));
        return minutes <= 1 ? 'Vừa xong' : `${minutes} phút trước`;
      }
      return `${hours} giờ trước`;
    }
    if (days === 1) return 'Hôm qua';
    if (days < 7) return `${days} ngày trước`;
    
    // Format with timezone
    return date.toLocaleDateString('vi-VN', { timeZone: timezone });
  }

  getWaitingDays(dateStr: string): number {
    if (!dateStr) return 0;
    const date = this.parseUtcDate(dateStr);
    const now = new Date();
    return Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
  }

  openSettings(): void {
    this.dialog.open(SettingsDialogComponent, { width: '600px', panelClass: 'settings-dialog' });
  }

  logout(): void {
    this.authService.logout();
    this.router.navigate(['/login']);
  }
}
