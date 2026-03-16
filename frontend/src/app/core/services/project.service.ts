import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { Project, SubPart, Tag } from '../models';

@Injectable({ providedIn: 'root' })
export class ProjectService {
  private readonly API = '/api/projects';

  constructor(private http: HttpClient) {}

  getProjects(): Observable<Project[]> {
    return this.http.get<Project[]>(this.API);
  }

  getProject(id: string): Observable<Project> {
    return this.http.get<Project>(`${this.API}/${id}`);
  }

  createProject(data: { 
    name: string; 
    description: string; 
    project_type?: 'video' | 'image';
    task_type?: 'object_detection' | 'classification' | 'captioning' | 'qa' | 'segmentation';
  }): Observable<Project> {
    return this.http.post<Project>(this.API, data);
  }

  updateProject(id: string, data: Partial<Project>): Observable<Project> {
    return this.http.put<Project>(`${this.API}/${id}`, data);
  }

  deleteProject(id: string): Observable<any> {
    return this.http.delete(`${this.API}/${id}`);
  }

  createSubpart(projectId: string, data: { name: string; description: string; assigned_users: string[] }): Observable<SubPart> {
    return this.http.post<SubPart>(`${this.API}/${projectId}/subparts`, data);
  }

  updateSubpart(projectId: string, subpartId: string, data: Partial<SubPart>): Observable<SubPart> {
    return this.http.put<SubPart>(`${this.API}/${projectId}/subparts/${subpartId}`, data);
  }

  deleteSubpart(projectId: string, subpartId: string): Observable<any> {
    return this.http.delete(`${this.API}/${projectId}/subparts/${subpartId}`);
  }

  // Get project_id from subpart
  getSubpartProject(subpartId: string): Observable<string | null> {
    return this.http.get<{ project_id: string }>(`/api/images/subpart/${subpartId}/project`).pipe(
      map(res => res.project_id)
    );
  }

  // ---- Tags ----
  getTags(projectId: string): Observable<Tag[]> {
    return this.http.get<Tag[]>(`/api/tags/project/${projectId}`);
  }

  createTag(projectId: string, data: { name: string; color: string }): Observable<Tag> {
    return this.http.post<Tag>(`/api/tags/project/${projectId}`, data);
  }

  updateTag(tagId: string, data: Partial<Tag>): Observable<Tag> {
    return this.http.put<Tag>(`/api/tags/${tagId}`, data);
  }

  deleteTag(tagId: string): Observable<any> {
    return this.http.delete(`/api/tags/${tagId}`);
  }

  // ---- Export ----
  exportProject(projectId: string, format: 'json' | 'yolo' | 'coco' | 'csv'): Observable<any> {
    return this.http.get<any>(`${this.API}/${projectId}/export/${format}`);
  }
}
