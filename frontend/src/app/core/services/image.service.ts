import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ImageItem, ImageRegion, ImageQA, Caption, Category, SegmentationResponse, ImageQCStats, ImageClassification } from '../models';
import { DamService } from './dam.service';

@Injectable({ providedIn: 'root' })
export class ImageService {
  private readonly API = '/api/images';
  private readonly CATEGORIES_API = '/api/categories';

  constructor(private http: HttpClient, private dam: DamService) {}

  // ---- Images ----
  uploadImage(projectId: string, file: File, subpartId?: string, width?: number, height?: number): Observable<any> {
    const formData = new FormData();
    formData.append('image', file);
    formData.append('project_id', projectId);
    if (subpartId) formData.append('subpart_id', subpartId);
    if (width) formData.append('width', width.toString());
    if (height) formData.append('height', height.toString());
    return this.http.post(`${this.API}/upload`, formData);
  }

  uploadImagesBatch(projectId: string, files: File[], subpartId?: string): Observable<any> {
    const formData = new FormData();
    formData.append('project_id', projectId);
    if (subpartId) formData.append('subpart_id', subpartId);
    files.forEach(file => formData.append('images', file));
    return this.http.post(`${this.API}/upload-batch`, formData);
  }

  getProjectImages(projectId: string): Observable<ImageItem[]> {
    return this.http.get<ImageItem[]>(`${this.API}/project/${projectId}`);
  }

  getSubpartImages(subpartId: string): Observable<ImageItem[]> {
    return this.http.get<ImageItem[]>(`${this.API}/subpart/${subpartId}`);
  }

  getImage(imageId: string): Observable<ImageItem> {
    return this.http.get<ImageItem>(`${this.API}/${imageId}`);
  }

  updateImage(imageId: string, data: Partial<ImageItem>): Observable<any> {
    return this.http.put(`${this.API}/${imageId}`, data);
  }

  deleteImage(imageId: string): Observable<any> {
    return this.http.delete(`${this.API}/${imageId}`);
  }

  // ---- Regions (Segmentation/Detection) ----
  getImageRegions(imageId: string): Observable<ImageRegion[]> {
    return this.http.get<ImageRegion[]>(`${this.API}/${imageId}/regions`);
  }

  createRegion(imageId: string, data: Partial<ImageRegion>): Observable<ImageRegion> {
    return this.http.post<ImageRegion>(`${this.API}/${imageId}/regions`, data);
  }

  updateRegion(regionId: string, data: Partial<ImageRegion>): Observable<ImageRegion> {
    return this.http.put<ImageRegion>(`${this.API}/regions/${regionId}`, data);
  }

  deleteRegion(regionId: string): Observable<any> {
    return this.http.delete(`${this.API}/regions/${regionId}`);
  }

  segmentObject(brushMask: string, imageData?: string): Observable<SegmentationResponse> {
    return this.dam.segmentObject(brushMask, imageData);
  }

  // ---- Categories ----
  getProjectCategories(projectId: string): Observable<Category[]> {
    return this.http.get<Category[]>(`${this.CATEGORIES_API}/project/${projectId}`);
  }

  createCategory(projectId: string, data: Partial<Category>): Observable<Category> {
    return this.http.post<Category>(`${this.CATEGORIES_API}/project/${projectId}`, data);
  }

  updateCategory(categoryId: string, data: Partial<Category>): Observable<Category> {
    return this.http.put<Category>(`${this.CATEGORIES_API}/${categoryId}`, data);
  }

  deleteCategory(categoryId: string): Observable<any> {
    return this.http.delete(`${this.CATEGORIES_API}/${categoryId}`);
  }

  // ---- Image-level Captions ----
  getImageCaption(imageId: string): Observable<Caption> {
    return this.http.get<Caption>(`${this.API}/${imageId}/caption`);
  }

  saveImageCaption(imageId: string, data: Partial<Caption>): Observable<any> {
    return this.http.post(`${this.API}/${imageId}/caption`, data);
  }

  // ---- Region Captions ----
  getRegionCaption(regionId: string): Observable<Caption> {
    return this.http.get<Caption>(`${this.API}/regions/${regionId}/caption`);
  }

  saveRegionCaption(regionId: string, data: Partial<Caption>): Observable<any> {
    return this.http.post(`${this.API}/regions/${regionId}/caption`, data);
  }

  // ---- QA (Question & Answer) ----
  getImageQA(imageId: string): Observable<ImageQA[]> {
    return this.http.get<ImageQA[]>(`${this.API}/${imageId}/qa`);
  }

  createQA(imageId: string, data: Partial<ImageQA>): Observable<ImageQA> {
    return this.http.post<ImageQA>(`${this.API}/${imageId}/qa`, data);
  }

  updateQA(qaId: string, data: Partial<ImageQA>): Observable<ImageQA> {
    return this.http.put<ImageQA>(`${this.API}/qa/${qaId}`, data);
  }

  deleteQA(qaId: string): Observable<any> {
    return this.http.delete(`${this.API}/qa/${qaId}`);
  }

  // ---- Classification ----
  setClassification(imageId: string, classification: ImageClassification): Observable<any> {
    return this.http.post(`${this.API}/${imageId}/classification`, classification);
  }

  // ---- Review ----
  submitForReview(imageId: string): Observable<any> {
    return this.http.post(`${this.API}/${imageId}/review`, {});
  }

  approveImage(imageId: string, comment?: string): Observable<any> {
    return this.http.post(`${this.API}/${imageId}/review/approve`, { comment });
  }

  rejectImage(imageId: string, comment?: string): Observable<any> {
    return this.http.post(`${this.API}/${imageId}/review/reject`, { comment });
  }

  // ---- Export ----
  exportImageAnnotations(imageId: string): Observable<any> {
    return this.http.get(`${this.API}/export/${imageId}`);
  }

  // ---- QC Stats ----
  getQCStats(): Observable<ImageQCStats> {
    return this.http.get<ImageQCStats>(`${this.API}/qc-stats`);
  }

  // ---- AI Indexing ----
  /**
   * Index an image and its regions using DINOv2 embeddings
   */
  indexImage(imageId: string): Observable<{ success: boolean; indexed_count: number }> {
    return this.http.post<{ success: boolean; indexed_count: number }>(`${this.API}/${imageId}/index`, {});
  }

  /**
   * Batch index multiple images
   */
  indexImagesBatch(imageIds: string[]): Observable<{
    results: { image_id: string; success: boolean; error?: string }[];
    total: number;
    success_count: number;
  }> {
    return this.http.post<any>(`${this.API}/index/batch`, { image_ids: imageIds });
  }

  /**
   * Search for similar images/regions using an image query
   */
  searchByImage(queryImage: string, options?: {
    query_mask?: string;
    top_k?: number;
    entity_types?: ('image' | 'object')[];
  }): Observable<ImageSearchResult> {
    return this.http.post<ImageSearchResult>(`${this.API}/search`, {
      query_image: queryImage,
      ...options
    });
  }
}

// ---- Types for AI Search ----
export interface ImageSearchResult {
  results: ImageSearchMatch[];
  total: number;
}

export interface ImageSearchMatch {
  entity_type: 'image' | 'object';
  score: number;
  image?: ImageItem;
  region?: {
    id: string;
    label: string;
    color: string;
    points: { x: number; y: number }[];
  };
}
