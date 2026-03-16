import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatDialogRef, MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ProjectService } from '../../core/services/project.service';
import { Project } from '../../core/models';

@Component({
  selector: 'app-edit-project-dialog',
  standalone: true,
  imports: [
    CommonModule, FormsModule, MatDialogModule,
    MatFormFieldModule, MatInputModule, MatSelectModule,
    MatButtonModule, MatIconModule, MatSnackBarModule
  ],
  template: `
    <h2 mat-dialog-title>Edit Project</h2>
    <mat-dialog-content>
      <mat-form-field appearance="outline" class="full-width">
        <mat-label>Project Name</mat-label>
        <input matInput [(ngModel)]="projectData.name" required />
      </mat-form-field>

      <mat-form-field appearance="outline" class="full-width">
        <mat-label>Description</mat-label>
        <textarea matInput [(ngModel)]="projectData.description" rows="3"></textarea>
      </mat-form-field>

      <mat-form-field appearance="outline" class="full-width">
        <mat-label>Task Type</mat-label>
        <mat-select [(ngModel)]="projectData.task_type">
          <mat-option value="object_detection">Object Detection</mat-option>
          <mat-option value="segmentation">Segmentation</mat-option>
          <mat-option value="classification">Classification</mat-option>
          <mat-option value="captioning">Captioning</mat-option>
          <mat-option value="qa">Q&A</mat-option>
        </mat-select>
      </mat-form-field>

      <mat-form-field appearance="outline" class="full-width">
        <mat-label>Status</mat-label>
        <mat-select [(ngModel)]="projectData.status">
          <mat-option value="active">Active</mat-option>
          <mat-option value="completed">Completed</mat-option>
          <mat-option value="archived">Archived</mat-option>
        </mat-select>
      </mat-form-field>
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button (click)="cancel()">Cancel</button>
      <button mat-flat-button color="primary" (click)="save()" [disabled]="saving || !projectData.name">
        {{ saving ? 'Saving...' : 'Save' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    mat-dialog-content {
      min-width: 400px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .full-width {
      width: 100%;
    }
  `]
})
export class EditProjectDialogComponent {
  projectData: {
    name: string;
    description: string;
    task_type: 'object_detection' | 'classification' | 'captioning' | 'qa' | 'segmentation';
    status: string;
  };
  saving = false;

  constructor(
    private dialogRef: MatDialogRef<EditProjectDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: { project: Project },
    private projectService: ProjectService,
    private snackBar: MatSnackBar
  ) {
    this.projectData = {
      name: data.project.name,
      description: data.project.description || '',
      task_type: data.project.task_type || 'object_detection' as const,
      status: data.project.status || 'active'
    };
  }

  save(): void {
    if (!this.projectData.name.trim()) return;

    this.saving = true;
    this.projectService.updateProject(this.data.project.id, this.projectData).subscribe({
      next: (updatedProject) => {
        this.saving = false;
        this.dialogRef.close(updatedProject);
      },
      error: (err) => {
        this.saving = false;
        this.snackBar.open(err.error?.error || 'Failed to update project', '', { duration: 3000 });
      }
    });
  }

  cancel(): void {
    this.dialogRef.close();
  }
}
