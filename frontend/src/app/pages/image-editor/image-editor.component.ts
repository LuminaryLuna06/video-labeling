import { Component, OnInit, ViewChild, ElementRef, OnDestroy, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatMenuModule } from '@angular/material/menu';
import { MatTabsModule } from '@angular/material/tabs';
import { MatChipsModule } from '@angular/material/chips';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatExpansionModule } from '@angular/material/expansion';
import { ImageService } from '../../core/services/image.service';
import { ProjectService } from '../../core/services/project.service';
import { AuthService } from '../../core/services/auth.service';
import { GeminiService } from '../../core/services/gemini.service';
import { SettingsService } from '../../core/services/settings.service';
import { KnowledgeBaseService } from '../../core/services/knowledge-base.service';
import { SettingsDialogComponent } from '../settings-dialog/settings-dialog.component';
import { EditProjectDialogComponent } from '../edit-project-dialog/edit-project-dialog.component';
import { KnowledgeBaseSelectorComponent } from '../../core/components/knowledge-base-selector/knowledge-base-selector.component';
import { ImageItem, ImageRegion, ImageQA, Caption, Category, ImageClassification, Project } from '../../core/models';

@Component({
  selector: 'app-image-editor',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatButtonModule, MatIconModule, MatFormFieldModule,
    MatInputModule, MatSelectModule, MatSnackBarModule, MatProgressSpinnerModule,
    MatTooltipModule, MatMenuModule, MatTabsModule, MatChipsModule, MatDialogModule,
    MatExpansionModule, KnowledgeBaseSelectorComponent
  ],
  templateUrl: './image-editor.component.html',
  styleUrls: ['./image-editor.component.scss']
})
export class ImageEditorComponent implements OnInit, OnDestroy {
  @ViewChild('imageCanvas') imageCanvasRef!: ElementRef<HTMLCanvasElement>;
  @ViewChild('drawCanvas') drawCanvasRef!: ElementRef<HTMLCanvasElement>;
  @ViewChild('maskCanvas') maskCanvasRef!: ElementRef<HTMLCanvasElement>;
  @ViewChild('canvasArea') canvasAreaRef!: ElementRef<HTMLDivElement>;

  image: ImageItem | null = null;
  project: Project | null = null;
  projectLoading = true; // Prevent showing wrong UI before project loads
  
  // Image navigation
  projectImages: ImageItem[] = [];
  currentImageIndex = 0;
  get hasPreviousImage(): boolean { return this.currentImageIndex > 0; }
  get hasNextImage(): boolean { return this.currentImageIndex < this.projectImages.length - 1; }
  
  // Task type configuration
  taskType: 'object_detection' | 'classification' | 'captioning' | 'qa' | 'segmentation' | null = null;
  singleTaskMode = true; // Default to true, will be set to false for video projects
  
  // Steps configuration - will be set based on task_type
  steps: string[] = [];
  currentStep = 1;

  // Regions
  regions: ImageRegion[] = [];
  selectedRegion: ImageRegion | null = null;
  brushMode: 'draw' | 'erase' | 'bbox' = 'bbox';
  activeTool: 'bbox' | 'brush' | 'eraser' = 'bbox';
  brushSize = 25;
  isDrawing = false;
  hasDrawing = false;
  segmenting = false;
  currentRegionLabel = 'Object';
  currentRegionColor = '#FF4444';
  lastSegmentedMask = '';
  private regionColors = ['#FF4444', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#14b8a6'];
  private regionColorIndex = 0;

  // Labels from existing regions
  defaultLabels: string[] = ['Person', 'Car', 'Building', 'Tree', 'Animal', 'Object'];
  showAddLabelInput = false;
  newLabelName = '';

  // Computed unique labels from ALL images in project (regions + classification + defaults)
  get uniqueLabels(): string[] {
    const allLabels: string[] = [...this.defaultLabels];
    
    // Get labels from all project images
    for (const img of this.projectImages) {
      // Labels from regions (using region_labels from API)
      if (img.region_labels) {
        allLabels.push(...img.region_labels);
      }
      // Labels from classification
      if (img.classification?.labels) {
        allLabels.push(...img.classification.labels);
      }
    }
    
    // Also include current image's regions (in case not in projectImages yet)
    for (const region of this.regions) {
      if (region.label) {
        allLabels.push(region.label);
      }
    }
    
    return [...new Set(allLabels)];
  }

  // Inline editing
  editingRegionId: string | null = null;
  editingRegionLabel = '';
  editingRegionColor = '';

  // Bounding box drawing
  bboxStart: { x: number; y: number } | null = null;
  bboxEnd: { x: number; y: number } | null = null;
  isDrawingBbox = false;

  // Zoom & Pan
  zoomLevel = 1;
  panX = 0;
  panY = 0;
  panMode = false;
  private isPanning = false;
  private panStartX = 0;
  private panStartY = 0;
  private panOriginX = 0;
  private panOriginY = 0;
  spaceHeld = false;

  // Classification
  classification: ImageClassification = {
    labels: [],
    primary_label: '',
    notes: ''
  };
  newClassLabel = '';
  commonLabels = ['Person', 'Vehicle', 'Building', 'Nature', 'Animal', 'Food', 'Object', 'Text'];

  // Captions
  imageCaptionData: Caption = {
    visual_caption: '',
    contextual_caption: '',
    knowledge_caption: '',
    combined_caption: '',
    visual_caption_vi: '',
    contextual_caption_vi: '',
    knowledge_caption_vi: '',
    combined_caption_vi: ''
  };
  regionCaptionData: Caption = {
    visual_caption: '',
    contextual_caption: '',
    knowledge_caption: '',
    combined_caption: '',
    visual_caption_vi: '',
    contextual_caption_vi: '',
    knowledge_caption_vi: '',
    combined_caption_vi: ''
  };
  captionKBIds: string[] = [];
  imageCaptionKBIds: string[] = [];

  // KB linkage for Object Detection
  imageKBIds: string[] = [];           // KB IDs for the image itself
  selectedRegionKBIds: string[] = [];  // KB IDs for the currently selected region

  // QA
  qaPairs: ImageQA[] = [];
  newQuestion = '';
  newAnswer = '';
  newQuestionVi = '';
  newAnswerVi = '';
  newQaType = 'general';
  qaTypes = ['general', 'visual', 'contextual', 'knowledge', 'counting', 'spatial', 'color', 'action'];
  editingQaId: string | null = null;

  // Panel resize
  panelWidth = parseInt(localStorage.getItem('imageEditorPanelWidth') || '320', 10);
  private isResizingPanel = false;

  // Review
  showRejectDialog = false;
  rejectComment = '';

  // Categories
  categories: Category[] = [];
  showCategoryDropdown = false;
  showInlineCategoryAdd = false;
  newCategoryName = '';
  newCategoryColor = '#3b82f6';

  // Generation flags
  translating = false;
  generatingCaption = false;

  private resizeMouseMove: ((e: MouseEvent) => void) | null = null;
  private resizeMouseUp: (() => void) | null = null;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private imageService: ImageService,
    private projectService: ProjectService,
    private authService: AuthService,
    private geminiService: GeminiService,
    private settingsService: SettingsService,
    private kbService: KnowledgeBaseService,
    private dialog: MatDialog,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    // Subscribe to route params for navigation between images
    this.route.paramMap.subscribe(params => {
      const imageId = params.get('imageId');
      if (imageId) {
        this.loadImage(imageId);
      }
    });
  }

  ngOnDestroy(): void {
    this.stopPanelResize();
  }

  loadImage(imageId: string): void {
    this.imageService.getImage(imageId).subscribe({
      next: (image) => {
        this.image = image;
        this.regions = image.regions || [];
        this.qaPairs = image.qa_pairs || [];
        this.classification = image.classification || { labels: [], primary_label: '', notes: '' };
        this.imageKBIds = image.knowledge_base_ids || [];
        this.selectedRegion = null;
        this.selectedRegionKBIds = [];
        
        if (image.image_caption) {
          this.imageCaptionData = { ...image.image_caption };
          this.imageCaptionKBIds = image.image_caption.knowledge_base_ids || [];
        } else {
          this.imageCaptionKBIds = [];
        }

        // Load project to get task_type and images list
        if (image.project_id) {
          this.loadProject(image.project_id);
          this.loadCategories(image.project_id);
          this.loadProjectImages(image.project_id, imageId);
        } else if (image.subpart_id) {
          // If no project_id but has subpart_id, get project from subpart
          this.loadProjectFromSubpart(image.subpart_id, imageId);
        } else {
          // Default to all steps if no project
          this.projectLoading = false;
          this.configureSteps();
          this.currentStep = image.current_step || 1;
        }

        // Draw image after view init
        setTimeout(() => this.drawImage(), 100);
      },
      error: () => {
        this.snackBar.open('Failed to load image', 'Close', { duration: 3000 });
        this.router.navigate(['/dashboard']);
      }
    });
  }

  loadProject(projectId: string): void {
    this.projectService.getProject(projectId).subscribe({
      next: (project) => {
        this.project = project;
        this.projectLoading = false;
        
        // For image projects, use task_type; for video projects, use multi-step
        if (project.project_type === 'image' && project.task_type) {
          this.taskType = project.task_type;
          this.singleTaskMode = true;
        } else if (project.project_type === 'video') {
          // Video projects use multi-step workflow
          this.singleTaskMode = false;
        } else {
          // Image project without task_type (old projects) - default to object_detection
          this.taskType = 'object_detection';
          this.singleTaskMode = true;
        }
        
        this.configureSteps();
        this.currentStep = this.singleTaskMode ? 1 : (this.image?.current_step || 1);
      },
      error: () => {
        this.projectLoading = false;
        // Fallback to all steps
        this.singleTaskMode = false;
        this.configureSteps();
        this.currentStep = this.image?.current_step || 1;
      }
    });
  }

  loadProjectFromSubpart(subpartId: string, currentImageId: string): void {
    // Get subpart to find project_id
    this.projectService.getSubpartProject(subpartId).subscribe({
      next: (projectId) => {
        if (projectId) {
          this.loadProject(projectId);
          this.loadCategories(projectId);
          this.loadProjectImages(projectId, currentImageId);
        } else {
          this.projectLoading = false;
          this.configureSteps();
          // Load images from subpart instead
          this.loadSubpartImages(subpartId, currentImageId);
        }
      },
      error: () => {
        this.projectLoading = false;
        this.configureSteps();
        // Load images from subpart instead
        this.loadSubpartImages(subpartId, currentImageId);
      }
    });
  }

  loadSubpartImages(subpartId: string, currentImageId: string): void {
    this.imageService.getSubpartImages(subpartId).subscribe({
      next: (images) => {
        this.projectImages = images;
        this.currentImageIndex = images.findIndex(img => img.id === currentImageId);
        if (this.currentImageIndex < 0) this.currentImageIndex = 0;
      }
    });
  }

  loadProjectImages(projectId: string, currentImageId: string): void {
    this.imageService.getProjectImages(projectId).subscribe({
      next: (images) => {
        this.projectImages = images;
        this.currentImageIndex = images.findIndex(img => img.id === currentImageId);
        if (this.currentImageIndex < 0) this.currentImageIndex = 0;
      }
    });
  }

  goToPreviousImage(): void {
    if (this.hasPreviousImage) {
      const prevImage = this.projectImages[this.currentImageIndex - 1];
      this.router.navigate(['/image-editor', prevImage.id]);
    }
  }

  goToNextImage(): void {
    if (this.hasNextImage) {
      const nextImage = this.projectImages[this.currentImageIndex + 1];
      this.router.navigate(['/image-editor', nextImage.id]);
    }
  }

  @HostListener('window:keydown', ['$event'])
  handleKeyboardNav(event: KeyboardEvent): void {
    // Arrow key navigation (without modifiers to avoid conflicts)
    if (!event.ctrlKey && !event.metaKey && !event.altKey) {
      if (event.key === 'ArrowLeft' && this.hasPreviousImage) {
        event.preventDefault();
        this.goToPreviousImage();
      } else if (event.key === 'ArrowRight' && this.hasNextImage) {
        event.preventDefault();
        this.goToNextImage();
      }
    }
  }

  configureSteps(): void {
    if (this.singleTaskMode && this.taskType) {
      // Single task mode - show only selected task
      switch (this.taskType) {
        case 'object_detection':
          this.steps = ['Object Detection'];
          break;
        case 'classification':
          this.steps = ['Classification'];
          break;
        case 'captioning':
          this.steps = ['Captioning'];
          break;
        case 'qa':
          this.steps = ['QA'];
          break;
        case 'segmentation':
          this.steps = ['Segmentation'];
          break;
      }
    } else {
      // Multi-task mode (video projects or no task_type)
      this.steps = ['Object Detection', 'Classification', 'Captioning', 'QA'];
    }
  }

  // Get the actual step type for current step (used for panel display)
  getCurrentStepType(): 'object_detection' | 'classification' | 'captioning' | 'qa' | 'segmentation' {
    if (this.singleTaskMode && this.taskType) {
      return this.taskType;
    }
    // Multi-step mode - map currentStep to type
    const stepMap: ('object_detection' | 'classification' | 'captioning' | 'qa')[] = 
      ['object_detection', 'classification', 'captioning', 'qa'];
    return stepMap[this.currentStep - 1] || 'object_detection';
  }

  setBrushMode(mode: 'draw' | 'erase' | 'bbox'): void {
    this.brushMode = mode;
    this.panMode = false;
  }

  loadCategories(projectId: string): void {
    this.imageService.getProjectCategories(projectId).subscribe({
      next: (categories) => {
        this.categories = categories;
      }
    });
  }

  drawImage(): void {
    if (!this.imageCanvasRef?.nativeElement || !this.image) return;

    const canvas = this.imageCanvasRef.nativeElement;
    const ctx = canvas.getContext('2d')!;
    const img = new Image();
    
    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);

      // Initialize other canvases
      if (this.drawCanvasRef?.nativeElement) {
        this.drawCanvasRef.nativeElement.width = img.width;
        this.drawCanvasRef.nativeElement.height = img.height;
      }
      if (this.maskCanvasRef?.nativeElement) {
        this.maskCanvasRef.nativeElement.width = img.width;
        this.maskCanvasRef.nativeElement.height = img.height;
      }

      // Calculate initial zoom to fit 90% of canvas area
      this.fitToScreen();

      this.drawRegionOverlays();
    };
    
    img.src = this.image.url;
  }

  fitToScreen(): void {
    if (!this.canvasAreaRef?.nativeElement || !this.imageCanvasRef?.nativeElement) return;
    
    const areaRect = this.canvasAreaRef.nativeElement.getBoundingClientRect();
    const imgWidth = this.imageCanvasRef.nativeElement.width;
    const imgHeight = this.imageCanvasRef.nativeElement.height;
    
    if (imgWidth === 0 || imgHeight === 0) return;
    
    // Calculate zoom to fit 90% of the available area
    const targetWidth = areaRect.width * 0.9;
    const targetHeight = areaRect.height * 0.9;
    
    const scaleX = targetWidth / imgWidth;
    const scaleY = targetHeight / imgHeight;
    
    // Use the smaller scale to ensure image fits
    this.zoomLevel = Math.min(scaleX, scaleY, 1); // Cap at 100%
    this.panX = 0;
    this.panY = 0;
  }

  drawRegionOverlays(): void {
    if (!this.maskCanvasRef?.nativeElement) return;

    const canvas = this.maskCanvasRef.nativeElement;
    const ctx = canvas.getContext('2d')!;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    for (const region of this.regions) {
      const isSelected = this.selectedRegion?.id === region.id;
      
      // Draw segmentation mask with region color
      if (region.segmentation_mask) {
        const img = new Image();
        img.onload = () => {
          // Create a temporary canvas to colorize the mask
          const tempCanvas = document.createElement('canvas');
          tempCanvas.width = canvas.width;
          tempCanvas.height = canvas.height;
          const tempCtx = tempCanvas.getContext('2d')!;
          
          // Draw the original mask
          tempCtx.drawImage(img, 0, 0);
          
          // Get image data and colorize it
          const imageData = tempCtx.getImageData(0, 0, tempCanvas.width, tempCanvas.height);
          const data = imageData.data;
          
          // Parse region color (hex to RGB)
          const hex = region.color.replace('#', '');
          const r = parseInt(hex.substring(0, 2), 16);
          const g = parseInt(hex.substring(2, 4), 16);
          const b = parseInt(hex.substring(4, 6), 16);
          
          // Colorize: replace white/bright pixels with region color
          for (let i = 0; i < data.length; i += 4) {
            // Check if pixel is not transparent and is bright (mask area)
            if (data[i + 3] > 0 && (data[i] > 100 || data[i + 1] > 100 || data[i + 2] > 100)) {
              data[i] = r;
              data[i + 1] = g;
              data[i + 2] = b;
              // Set alpha based on selection state
              data[i + 3] = isSelected ? 180 : 100;
            } else {
              // Make non-mask areas transparent
              data[i + 3] = 0;
            }
          }
          
          tempCtx.putImageData(imageData, 0, 0);
          
          // Draw to main canvas
          ctx.drawImage(tempCanvas, 0, 0);
        };
        img.src = region.segmentation_mask;
      }

      // Draw bounding box
      if (region.bbox && region.bbox.length === 4) {
        const [x, y, w, h] = region.bbox;
        ctx.strokeStyle = region.color;
        ctx.lineWidth = isSelected ? 4 : 2;
        ctx.strokeRect(x, y, w, h);
        
        // Fill with semi-transparent color if selected
        if (isSelected) {
          ctx.fillStyle = region.color + '40'; // 25% opacity
          ctx.fillRect(x, y, w, h);
        }

        // Draw label background
        const labelText = region.label;
        ctx.font = '14px Arial';
        const textWidth = ctx.measureText(labelText).width;
        ctx.fillStyle = region.color;
        ctx.fillRect(x, y - 25, textWidth + 10, 25);
        
        // Draw label text
        ctx.fillStyle = '#fff';
        ctx.fillText(labelText, x + 5, y - 7);
      }
    }
  }

  // ============ DRAWING ============

  startDraw(event: MouseEvent): void {
    const stepType = this.getCurrentStepType();
    if (stepType !== 'object_detection' && stepType !== 'segmentation' && stepType !== 'captioning') return;
    
    const canvas = this.drawCanvasRef?.nativeElement;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (event.clientX - rect.left) * scaleX;
    const y = (event.clientY - rect.top) * scaleY;

    // Object detection: only bounding box
    // Segmentation: only brush
    // Captioning: can use bbox, brush or eraser based on activeTool
    if (stepType === 'object_detection') {
      this.isDrawingBbox = true;
      this.bboxStart = { x, y };
      this.bboxEnd = { x, y };
    } else if (stepType === 'segmentation') {
      this.isDrawing = true;
      const ctx = canvas.getContext('2d')!;
      ctx.beginPath();
      ctx.moveTo(x, y);
    } else if (stepType === 'captioning') {
      if (this.activeTool === 'bbox') {
        this.isDrawingBbox = true;
        this.bboxStart = { x, y };
        this.bboxEnd = { x, y };
      } else if (this.activeTool === 'brush' || this.activeTool === 'eraser') {
        this.isDrawing = true;
        const ctx = canvas.getContext('2d')!;
        ctx.beginPath();
        ctx.moveTo(x, y);
      }
    }
  }

  draw(event: MouseEvent): void {
    const canvas = this.drawCanvasRef?.nativeElement;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (event.clientX - rect.left) * scaleX;
    const y = (event.clientY - rect.top) * scaleY;

    if (this.isDrawingBbox && this.bboxStart) {
      this.bboxEnd = { x, y };
      this.drawBboxPreview();
    } else if (this.isDrawing) {
      const ctx = canvas.getContext('2d')!;
      ctx.lineTo(x, y);
      // Check eraser mode for both segmentation and captioning
      const isErasing = this.brushMode === 'erase' || this.activeTool === 'eraser';
      ctx.strokeStyle = isErasing ? '#000' : this.currentRegionColor;
      ctx.lineWidth = this.brushSize;
      ctx.lineCap = 'round';
      ctx.globalCompositeOperation = isErasing ? 'destination-out' : 'source-over';
      ctx.stroke();
      this.hasDrawing = true;
    }
  }

  stopDraw(): void {
    if (this.isDrawingBbox && this.bboxStart && this.bboxEnd) {
      this.finalizeBbox();
    }
    this.isDrawing = false;
    this.isDrawingBbox = false;
  }

  drawBboxPreview(): void {
    if (!this.drawCanvasRef?.nativeElement || !this.bboxStart || !this.bboxEnd) return;

    const canvas = this.drawCanvasRef.nativeElement;
    const ctx = canvas.getContext('2d')!;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const x = Math.min(this.bboxStart.x, this.bboxEnd.x);
    const y = Math.min(this.bboxStart.y, this.bboxEnd.y);
    const w = Math.abs(this.bboxEnd.x - this.bboxStart.x);
    const h = Math.abs(this.bboxEnd.y - this.bboxStart.y);

    ctx.strokeStyle = this.currentRegionColor;
    ctx.lineWidth = 2;
    ctx.setLineDash([5, 5]);
    ctx.strokeRect(x, y, w, h);
    ctx.setLineDash([]);
  }

  finalizeBbox(): void {
    if (!this.bboxStart || !this.bboxEnd || !this.image) return;

    const x = Math.min(this.bboxStart.x, this.bboxEnd.x);
    const y = Math.min(this.bboxStart.y, this.bboxEnd.y);
    const w = Math.abs(this.bboxEnd.x - this.bboxStart.x);
    const h = Math.abs(this.bboxEnd.y - this.bboxStart.y);

    if (w < 10 || h < 10) {
      this.bboxStart = null;
      this.bboxEnd = null;
      return;
    }

    // Create region with bbox
    const regionData = {
      label: this.currentRegionLabel,
      color: this.currentRegionColor,
      bbox: [x, y, w, h]
    };

    this.imageService.createRegion(this.image.id, regionData).subscribe({
      next: (region) => {
        this.regions.push(region);
        this.selectRegion(region);
        this.nextRegionColor();
        this.clearDrawCanvas();
        this.drawRegionOverlays();
        this.snackBar.open('Region created', 'Close', { duration: 2000 });
      },
      error: () => {
        this.snackBar.open('Failed to create region', 'Close', { duration: 3000 });
      }
    });

    this.bboxStart = null;
    this.bboxEnd = null;
  }

  clearDrawCanvas(): void {
    if (!this.drawCanvasRef?.nativeElement) return;
    const ctx = this.drawCanvasRef.nativeElement.getContext('2d')!;
    ctx.clearRect(0, 0, this.drawCanvasRef.nativeElement.width, this.drawCanvasRef.nativeElement.height);
    this.hasDrawing = false;
  }

  // ============ SEGMENTATION ============

  async segmentObject(): Promise<void> {
    if (!this.hasDrawing || !this.image || this.segmenting) return;

    this.segmenting = true;
    const brushMask = this.drawCanvasRef.nativeElement.toDataURL('image/png');
    const imageData = this.imageCanvasRef.nativeElement.toDataURL('image/png');

    this.imageService.segmentObject(brushMask, imageData).subscribe({
      next: (response) => {
        this.lastSegmentedMask = response.segmented_mask;
        this.saveRegionWithMask();
        this.segmenting = false;
      },
      error: (err) => {
        const errorMsg = err?.error?.error || 'Segmentation failed';
        this.snackBar.open(errorMsg, 'Close', { duration: 3000 });
        this.segmenting = false;
      }
    });
  }

  async saveRegionWithMask(): Promise<void> {
    if (!this.image) return;

    // For object_detection task, extract bounding box from segmentation mask
    const isObjectDetection = this.getCurrentStepType() === 'object_detection';
    
    let regionData: any = {
      label: this.currentRegionLabel,
      color: this.currentRegionColor,
      brush_mask: this.drawCanvasRef.nativeElement.toDataURL('image/png'),
      segmentation_mask: this.lastSegmentedMask
    };

    // If object_detection, compute bounding box from segmentation mask
    if (isObjectDetection && this.lastSegmentedMask) {
      try {
        const bbox = await this.extractBboxFromMask(this.lastSegmentedMask);
        if (bbox) {
          regionData.bbox = bbox;
        }
      } catch (e) {
        console.error('Failed to extract bbox from mask', e);
      }
    }

    this.imageService.createRegion(this.image.id, regionData).subscribe({
      next: (region) => {
        this.regions.push(region);
        this.selectRegion(region);
        this.nextRegionColor();
        this.clearDrawCanvas();
        this.drawRegionOverlays();
        this.snackBar.open('Region saved', 'Close', { duration: 2000 });
      },
      error: () => {
        this.snackBar.open('Failed to save region', 'Close', { duration: 3000 });
      }
    });
  }

  extractBboxFromMask(maskDataUrl: string): Promise<number[] | null> {
    return new Promise((resolve) => {
      const img = new Image();
      
      img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = this.imageCanvasRef.nativeElement.width;
        canvas.height = this.imageCanvasRef.nativeElement.height;
        const ctx = canvas.getContext('2d')!;
        
        // Now the image is loaded, we can draw it
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const data = imageData.data;
        
        let minX = canvas.width, minY = canvas.height, maxX = 0, maxY = 0;
        let hasPixels = false;
        
        for (let y = 0; y < canvas.height; y++) {
          for (let x = 0; x < canvas.width; x++) {
            const idx = (y * canvas.width + x) * 4;
            // Check if pixel is non-black (mask area)
            if (data[idx] > 128 || data[idx + 1] > 128 || data[idx + 2] > 128 || data[idx + 3] > 128) {
              hasPixels = true;
              if (x < minX) minX = x;
              if (x > maxX) maxX = x;
              if (y < minY) minY = y;
              if (y > maxY) maxY = y;
            }
          }
        }
        
        if (!hasPixels) {
          resolve(null);
          return;
        }
        
        const width = maxX - minX;
        const height = maxY - minY;
        
        if (width < 5 || height < 5) {
          resolve(null);
          return;
        }
        
        resolve([minX, minY, width, height]);
      };
      
      img.onerror = () => {
        resolve(null);
      };
      
      img.src = maskDataUrl;
    });
  }

  selectRegion(region: ImageRegion): void {
    this.selectedRegion = region;
    this.currentRegionLabel = region.label;
    this.currentRegionColor = region.color;
    this.selectedRegionKBIds = region.knowledge_base_ids || [];

    // Load region caption
    if (region.caption) {
      this.regionCaptionData = { ...region.caption };
      this.captionKBIds = region.caption.knowledge_base_ids || [];
    } else {
      this.regionCaptionData = {
        visual_caption: '',
        contextual_caption: '',
        knowledge_caption: '',
        combined_caption: '',
        visual_caption_vi: '',
        contextual_caption_vi: '',
        knowledge_caption_vi: '',
        combined_caption_vi: ''
      };
      this.captionKBIds = [];
    }

    this.drawRegionOverlays();
  }

  // ============ PREDEFINED LABELS ============

  selectPredefinedLabel(label: string): void {
    this.currentRegionLabel = label;
  }

  addPredefinedLabel(): void {
    const label = this.newLabelName.trim();
    if (label && !this.defaultLabels.includes(label)) {
      this.defaultLabels.push(label);
      this.currentRegionLabel = label;
      this.newLabelName = '';
      this.showAddLabelInput = false;
    } else if (label) {
      this.currentRegionLabel = label;
      this.newLabelName = '';
      this.showAddLabelInput = false;
    }
  }

  removePredefinedLabel(label: string): void {
    // Remove from default labels
    const index = this.defaultLabels.indexOf(label);
    if (index >= 0) {
      this.defaultLabels.splice(index, 1);
    }
    // If current label was removed, select another
    if (this.currentRegionLabel === label) {
      this.currentRegionLabel = this.uniqueLabels[0] || 'Object';
    }
  }

  addPredefinedLabelAndApplyToClassification(): void {
    const label = this.newLabelName.trim();
    if (label) {
      // Add to default labels if not exists
      if (!this.defaultLabels.includes(label)) {
        this.defaultLabels.push(label);
      }
      // Also add to classification labels
      this.addCommonLabel(label);
      this.newLabelName = '';
      this.showAddLabelInput = false;
    }
  }

  selectEditLabel(label: string): void {
    if (label === '__add_new__') {
      // Show input to add new label during edit
      return;
    }
    this.editingRegionLabel = label;
  }

  // ============ INLINE REGION EDITING ============

  startRegionEdit(region: ImageRegion): void {
    this.editingRegionId = region.id;
    this.editingRegionLabel = region.label;
    this.editingRegionColor = region.color;
  }

  saveRegionEdit(region: ImageRegion): void {
    if (!this.editingRegionLabel.trim()) {
      this.cancelRegionEdit();
      return;
    }

    this.imageService.updateRegion(region.id, {
      label: this.editingRegionLabel.trim(),
      color: this.editingRegionColor
    }).subscribe({
      next: (updated) => {
        const index = this.regions.findIndex(r => r.id === updated.id);
        if (index >= 0) {
          this.regions[index] = updated;
        }
        if (this.selectedRegion?.id === updated.id) {
          this.selectedRegion = updated;
          this.currentRegionLabel = updated.label;
          this.currentRegionColor = updated.color;
        }
        this.drawRegionOverlays();
        this.editingRegionId = null;
        this.snackBar.open('Region updated', 'Close', { duration: 2000 });
      }
    });
  }

  cancelRegionEdit(): void {
    this.editingRegionId = null;
    this.editingRegionLabel = '';
    this.editingRegionColor = '';
  }

  deleteRegion(region: ImageRegion): void {
    this.imageService.deleteRegion(region.id).subscribe({
      next: () => {
        this.regions = this.regions.filter(r => r.id !== region.id);
        if (this.selectedRegion?.id === region.id) {
          this.selectedRegion = null;
        }
        this.drawRegionOverlays();
        this.snackBar.open('Region deleted', 'Close', { duration: 2000 });
      }
    });
  }

  updateRegionLabel(): void {
    if (!this.selectedRegion) return;

    this.imageService.updateRegion(this.selectedRegion.id, {
      label: this.currentRegionLabel,
      color: this.currentRegionColor
    }).subscribe({
      next: (updated) => {
        const index = this.regions.findIndex(r => r.id === updated.id);
        if (index >= 0) {
          this.regions[index] = updated;
        }
        this.selectedRegion = updated;
        this.drawRegionOverlays();
      }
    });
  }

  nextRegionColor(): void {
    this.regionColorIndex = (this.regionColorIndex + 1) % this.regionColors.length;
    this.currentRegionColor = this.regionColors[this.regionColorIndex];
  }

  // ============ CLASSIFICATION ============

  addClassLabel(): void {
    if (!this.newClassLabel.trim()) return;
    
    if (!this.classification.labels.includes(this.newClassLabel.trim())) {
      this.classification.labels.push(this.newClassLabel.trim());
      if (!this.classification.primary_label) {
        this.classification.primary_label = this.newClassLabel.trim();
      }
    }
    this.newClassLabel = '';
    this.saveClassification();
  }

  addCommonLabel(label: string): void {
    if (!this.classification.labels.includes(label)) {
      this.classification.labels.push(label);
      if (!this.classification.primary_label) {
        this.classification.primary_label = label;
      }
      this.saveClassification();
    }
  }

  removeClassLabel(label: string): void {
    this.classification.labels = this.classification.labels.filter(l => l !== label);
    if (this.classification.primary_label === label) {
      this.classification.primary_label = this.classification.labels[0] || '';
    }
    this.saveClassification();
  }

  setPrimaryLabel(label: string): void {
    this.classification.primary_label = label;
    this.saveClassification();
  }

  saveClassification(): void {
    if (!this.image) return;

    this.imageService.setClassification(this.image.id, this.classification).subscribe({
      next: () => {
        this.snackBar.open('Classification saved', 'Close', { duration: 2000 });
      }
    });
  }

  // ============ CAPTIONS ============

  saveImageCaption(): void {
    if (!this.image) return;

    this.imageService.saveImageCaption(this.image.id, {
      ...this.imageCaptionData,
      knowledge_base_ids: this.imageCaptionKBIds
    }).subscribe({
      next: () => {
        this.snackBar.open('Image caption saved', 'Close', { duration: 2000 });
      }
    });
  }

  saveRegionCaption(): void {
    if (!this.selectedRegion) return;

    this.imageService.saveRegionCaption(this.selectedRegion.id, {
      ...this.regionCaptionData,
      knowledge_base_ids: this.captionKBIds
    }).subscribe({
      next: () => {
        this.snackBar.open('Region caption saved', 'Close', { duration: 2000 });
      }
    });
  }

  async translateCaption(source: 'en' | 'vi', target: 'en' | 'vi', isImage: boolean): Promise<void> {
    this.translating = true;
    const captionData = isImage ? this.imageCaptionData : this.regionCaptionData;
    const fields = ['visual', 'contextual', 'knowledge', 'combined'];
    const direction: 'en_to_vi' | 'vi_to_en' = source === 'en' ? 'en_to_vi' : 'vi_to_en';

    try {
      for (const field of fields) {
        const sourceField = source === 'en' ? `${field}_caption` : `${field}_caption_vi`;
        const targetField = target === 'en' ? `${field}_caption` : `${field}_caption_vi`;
        const sourceText = (captionData as any)[sourceField];

        if (sourceText) {
          const translated = await this.geminiService.translate(sourceText, direction);
          (captionData as any)[targetField] = translated || '';
        }
      }

      if (isImage) {
        this.saveImageCaption();
      } else {
        this.saveRegionCaption();
      }
    } catch (error) {
      this.snackBar.open('Translation failed', 'Close', { duration: 3000 });
    } finally {
      this.translating = false;
    }
  }

  /** Check if we can combine captions (for Image Caption) */
  canCombineImageCaptions(): boolean {
    const d = this.imageCaptionData;
    const hasSourceText = !!(d.visual_caption_vi || d.contextual_caption_vi);
    const hasKB = this.imageCaptionKBIds.length > 0;
    return hasSourceText && hasKB;
  }

  /** Check if we can combine captions (for Region Caption) */
  canCombineRegionCaptions(): boolean {
    const d = this.regionCaptionData;
    const hasSourceText = !!(d.visual_caption_vi || d.contextual_caption_vi);
    const hasKB = this.captionKBIds.length > 0;
    return hasSourceText && hasKB;
  }

  /** Get tooltip for combine button */
  getCombineTooltip(isImage: boolean): string {
    const d = isImage ? this.imageCaptionData : this.regionCaptionData;
    const kbIds = isImage ? this.imageCaptionKBIds : this.captionKBIds;
    if (!d.visual_caption_vi && !d.contextual_caption_vi) {
      return 'Cần nhập Visual Caption (VI) hoặc Contextual Caption (VI)';
    }
    if (kbIds.length === 0) {
      return 'Cần chọn Knowledge Base';
    }
    return 'Combine captions với Knowledge Base và dịch sang EN';
  }

  /** Auto combine + translate for Image Caption: Vietnamese first, then translate to English */
  async autoCombineAndTranslateImage(): Promise<void> {
    const d = this.imageCaptionData;

    if (!this.geminiService.isConfigured()) {
      this.snackBar.open('Gemini API key not set. Open Settings to configure.', 'Settings', {
        duration: 5000
      }).onAction().subscribe(() => this.openSettings());
      return;
    }

    this.translating = true;
    try {
      // Step 1: Get KB context (Vietnamese)
      let kbContextVi = '';
      if (this.imageCaptionKBIds.length > 0) {
        const contextData = await this.kbService.getContext(this.imageCaptionKBIds).toPromise();
        if (contextData) {
          kbContextVi = contextData.context_text_vi;
        }
      }

      // Step 2: Combine Vietnamese captions with KB context
      const partsVi: string[] = [];
      if (d.visual_caption_vi) partsVi.push(d.visual_caption_vi);
      if (d.contextual_caption_vi) partsVi.push(d.contextual_caption_vi);
      
      const combinedVi = await this.geminiService.combineCaptionsWithKnowledge(partsVi, kbContextVi, true);
      d.combined_caption_vi = combinedVi;

      // Step 3: Translate Vietnamese combined to English
      if (combinedVi) {
        const enResult = await this.geminiService.translateToEn(combinedVi);
        d.combined_caption = enResult;
      }

      this.saveImageCaption();
      this.snackBar.open('Combine & Translate thành công!', '', { duration: 2000 });
    } catch (err: any) {
      this.snackBar.open(err.message || 'Combine/Translate failed', '', { duration: 4000 });
    } finally {
      this.translating = false;
    }
  }

  /** Auto combine + translate for Region Caption */
  async autoCombineAndTranslateRegion(): Promise<void> {
    if (!this.selectedRegion) return;
    const d = this.regionCaptionData;

    if (!this.geminiService.isConfigured()) {
      this.snackBar.open('Gemini API key not set. Open Settings to configure.', 'Settings', {
        duration: 5000
      }).onAction().subscribe(() => this.openSettings());
      return;
    }

    this.translating = true;
    try {
      // Step 1: Get KB context (Vietnamese)
      let kbContextVi = '';
      if (this.captionKBIds.length > 0) {
        const contextData = await this.kbService.getContext(this.captionKBIds).toPromise();
        if (contextData) {
          kbContextVi = contextData.context_text_vi;
        }
      }

      // Step 2: Combine Vietnamese captions with KB context
      const partsVi: string[] = [];
      if (d.visual_caption_vi) partsVi.push(d.visual_caption_vi);
      if (d.contextual_caption_vi) partsVi.push(d.contextual_caption_vi);
      
      const combinedVi = await this.geminiService.combineCaptionsWithKnowledge(partsVi, kbContextVi, true);
      d.combined_caption_vi = combinedVi;

      // Step 3: Translate Vietnamese combined to English
      if (combinedVi) {
        const enResult = await this.geminiService.translateToEn(combinedVi);
        d.combined_caption = enResult;
      }

      this.saveRegionCaption();
      this.snackBar.open('Combine & Translate thành công!', '', { duration: 2000 });
    } catch (err: any) {
      this.snackBar.open(err.message || 'Combine/Translate failed', '', { duration: 4000 });
    } finally {
      this.translating = false;
    }
  }

  /** KB selection change for image caption */
  onImageKBSelectionChange(nodes: any[]): void {
    // selectionChange emits KBNode[], extract IDs
    this.imageCaptionKBIds = nodes.map(n => n.id);
  }

  /** KB selection change for region caption */
  onRegionKBSelectionChange(nodes: any[]): void {
    // selectionChange emits KBNode[], extract IDs
    this.captionKBIds = nodes.map(n => n.id);
  }

  /** KB selection change for image (Object Detection mode) */
  onImageKBChange(nodes: any[]): void {
    if (!this.image) return;
    this.imageKBIds = nodes.map(n => n.id);
    // Save to backend
    this.imageService.updateImage(this.image.id, { knowledge_base_ids: this.imageKBIds }).subscribe({
      next: () => {
        this.snackBar.open('Image KB updated', 'Close', { duration: 2000 });
      },
      error: () => {
        this.snackBar.open('Failed to update image KB', 'Close', { duration: 3000 });
      }
    });
  }

  /** KB selection change for region/object (Object Detection mode) */
  onRegionKBChange(nodes: any[]): void {
    if (!this.selectedRegion) return;
    this.selectedRegionKBIds = nodes.map(n => n.id);
    // Save to backend
    this.imageService.updateRegion(this.selectedRegion.id, { knowledge_base_ids: this.selectedRegionKBIds }).subscribe({
      next: (updatedRegion) => {
        // Update local region
        const idx = this.regions.findIndex(r => r.id === this.selectedRegion!.id);
        if (idx >= 0) {
          this.regions[idx].knowledge_base_ids = this.selectedRegionKBIds;
        }
        this.selectedRegion!.knowledge_base_ids = this.selectedRegionKBIds;
        this.snackBar.open('Object KB updated', 'Close', { duration: 2000 });
      },
      error: () => {
        this.snackBar.open('Failed to update object KB', 'Close', { duration: 3000 });
      }
    });
  }

  // ============ QA ============

  addQA(): void {
    if (!this.image || !this.newQuestion.trim()) return;

    const qaData = {
      question: this.newQuestion.trim(),
      answer: this.newAnswer.trim(),
      question_vi: this.newQuestionVi.trim(),
      answer_vi: this.newAnswerVi.trim(),
      qa_type: this.newQaType
    };

    this.imageService.createQA(this.image.id, qaData).subscribe({
      next: (qa) => {
        this.qaPairs.push(qa);
        this.clearQAForm();
        this.snackBar.open('QA added', 'Close', { duration: 2000 });
      }
    });
  }

  editQA(qa: ImageQA): void {
    this.editingQaId = qa.id;
    this.newQuestion = qa.question;
    this.newAnswer = qa.answer;
    this.newQuestionVi = qa.question_vi;
    this.newAnswerVi = qa.answer_vi;
    this.newQaType = qa.qa_type;
  }

  updateQA(): void {
    if (!this.editingQaId) return;

    const qaData = {
      question: this.newQuestion.trim(),
      answer: this.newAnswer.trim(),
      question_vi: this.newQuestionVi.trim(),
      answer_vi: this.newAnswerVi.trim(),
      qa_type: this.newQaType
    };

    this.imageService.updateQA(this.editingQaId, qaData).subscribe({
      next: (updated) => {
        const index = this.qaPairs.findIndex(q => q.id === updated.id);
        if (index >= 0) {
          this.qaPairs[index] = updated;
        }
        this.clearQAForm();
        this.snackBar.open('QA updated', 'Close', { duration: 2000 });
      }
    });
  }

  deleteQA(qa: ImageQA): void {
    this.imageService.deleteQA(qa.id).subscribe({
      next: () => {
        this.qaPairs = this.qaPairs.filter(q => q.id !== qa.id);
        this.snackBar.open('QA deleted', 'Close', { duration: 2000 });
      }
    });
  }

  clearQAForm(): void {
    this.editingQaId = null;
    this.newQuestion = '';
    this.newAnswer = '';
    this.newQuestionVi = '';
    this.newAnswerVi = '';
    this.newQaType = 'general';
  }

  // ============ NAVIGATION ============

  setStep(step: number): void {
    this.currentStep = step;
    this.saveProgress();
  }

  nextStep(): void {
    if (this.currentStep < this.steps.length) {
      this.currentStep++;
      this.saveProgress();
    }
  }

  prevStep(): void {
    if (this.currentStep > 1) {
      this.currentStep--;
      this.saveProgress();
    }
  }

  saveProgress(): void {
    if (!this.image) return;
    this.imageService.updateImage(this.image.id, { current_step: this.currentStep }).subscribe();
  }

  // ============ ZOOM & PAN ============

  @HostListener('window:keydown', ['$event'])
  onKeyDown(event: KeyboardEvent): void {
    // Don't trigger pan mode when typing in input/textarea
    const target = event.target as HTMLElement;
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
      return;
    }
    if (event.code === 'Space' && !this.spaceHeld) {
      this.spaceHeld = true;
      this.panMode = true;
      event.preventDefault();
    }
  }

  @HostListener('window:keyup', ['$event'])
  onKeyUp(event: KeyboardEvent): void {
    if (event.code === 'Space') {
      this.spaceHeld = false;
      this.panMode = false;
    }
  }

  zoomIn(): void {
    this.zoomLevel = Math.min(5, this.zoomLevel + 0.25);
  }

  zoomOut(): void {
    this.zoomLevel = Math.max(0.25, this.zoomLevel - 0.25);
  }

  resetZoom(): void {
    this.fitToScreen();
  }

  onWheel(event: WheelEvent): void {
    event.preventDefault();
    if (event.deltaY < 0) {
      this.zoomIn();
    } else {
      this.zoomOut();
    }
  }

  startPan(event: MouseEvent): void {
    if (!this.panMode) return;
    this.isPanning = true;
    this.panStartX = event.clientX;
    this.panStartY = event.clientY;
    this.panOriginX = this.panX;
    this.panOriginY = this.panY;
  }

  doPan(event: MouseEvent): void {
    if (!this.isPanning) return;
    this.panX = this.panOriginX + (event.clientX - this.panStartX);
    this.panY = this.panOriginY + (event.clientY - this.panStartY);
  }

  endPan(): void {
    this.isPanning = false;
  }

  // ============ PANEL RESIZE ============

  startPanelResize(event: MouseEvent): void {
    event.preventDefault();
    this.isResizingPanel = true;
    const startX = event.clientX;
    const startWidth = this.panelWidth;

    this.resizeMouseMove = (e: MouseEvent) => {
      const delta = startX - e.clientX;
      this.panelWidth = Math.max(250, Math.min(600, startWidth + delta));
    };

    this.resizeMouseUp = () => {
      this.stopPanelResize();
    };

    document.addEventListener('mousemove', this.resizeMouseMove);
    document.addEventListener('mouseup', this.resizeMouseUp);
  }

  stopPanelResize(): void {
    if (this.resizeMouseMove) {
      document.removeEventListener('mousemove', this.resizeMouseMove);
    }
    if (this.resizeMouseUp) {
      document.removeEventListener('mouseup', this.resizeMouseUp);
    }
    this.isResizingPanel = false;
    // Save panel width to localStorage
    localStorage.setItem('imageEditorPanelWidth', this.panelWidth.toString());
  }

  // ============ REVIEW ============

  submitForReview(): void {
    if (!this.image) return;
    this.imageService.submitForReview(this.image.id).subscribe({
      next: () => {
        this.image!.review_status = 'pending';
        this.snackBar.open('Submitted for review', 'Close', { duration: 2000 });
      }
    });
  }

  approveImage(): void {
    if (!this.image) return;
    this.imageService.approveImage(this.image.id).subscribe({
      next: () => {
        this.image!.review_status = 'approved';
        this.snackBar.open('Image approved', 'Close', { duration: 2000 });
      }
    });
  }

  openRejectDialog(): void {
    this.showRejectDialog = true;
  }

  rejectImage(): void {
    if (!this.image) return;
    this.imageService.rejectImage(this.image.id, this.rejectComment).subscribe({
      next: () => {
        this.image!.review_status = 'rejected';
        this.showRejectDialog = false;
        this.rejectComment = '';
        this.snackBar.open('Image rejected', 'Close', { duration: 2000 });
      }
    });
  }

  // ============ EXPORT ============

  exportAnnotations(): void {
    if (!this.image) return;
    this.imageService.exportImageAnnotations(this.image.id).subscribe({
      next: (data) => {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${this.image!.original_name}_annotations.json`;
        a.click();
        window.URL.revokeObjectURL(url);
      }
    });
  }

  exportProject(format: 'json' | 'yolo' | 'coco' | 'csv'): void {
    if (!this.project) return;
    
    this.projectService.exportProject(this.project.id, format).subscribe({
      next: (data) => {
        let blob: Blob;
        let filename: string;
        
        if (format === 'csv' && data.csv_content) {
          blob = new Blob([data.csv_content], { type: 'text/csv' });
          filename = `${this.project!.name}_${data.task_type}.csv`;
        } else if (format === 'yolo') {
          // YOLO format: create a zip-like structure as JSON
          blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
          filename = `${this.project!.name}_yolo.json`;
        } else if (format === 'coco') {
          blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
          filename = `${this.project!.name}_coco.json`;
        } else {
          blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
          filename = `${this.project!.name}_export.json`;
        }
        
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        window.URL.revokeObjectURL(url);
        
        this.snackBar.open(`Exported as ${format.toUpperCase()}`, '', { duration: 2000 });
      },
      error: (err) => {
        this.snackBar.open(err.error?.error || 'Export failed', '', { duration: 3000 });
      }
    });
  }

  openEditProjectDialog(): void {
    if (!this.project) return;
    
    const dialogRef = this.dialog.open(EditProjectDialogComponent, {
      width: '500px',
      data: { project: this.project }
    });

    dialogRef.afterClosed().subscribe((result) => {
      if (result) {
        this.project = result;
        this.snackBar.open('Project updated', '', { duration: 2000 });
      }
    });
  }

  // ============ UTILS ============

  openSettings(): void {
    this.dialog.open(SettingsDialogComponent, { width: '600px', panelClass: 'settings-dialog' });
  }

  goBack(): void {
    this.router.navigate(['/dashboard']);
  }

  get user() {
    return this.authService.user;
  }

  getCategoryColor(categoryId: string | undefined | null): string {
    if (!categoryId) return '#888';
    const cat = this.categories.find(c => c.id === categoryId);
    return cat?.color || '#888';
  }

  getReviewStatusClass(): string {
    switch (this.image?.review_status) {
      case 'approved': return 'status-approved';
      case 'rejected': return 'status-rejected';
      case 'pending': return 'status-pending';
      default: return 'status-not-submitted';
    }
  }
}
