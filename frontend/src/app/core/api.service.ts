import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { Campaign, Family, GraphData, MaterialRow, MaterialView, PairView, SystemStatus } from './models';

@Injectable({ providedIn: 'root' })
export class Api {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/v1';

  status(): Observable<SystemStatus> {
    return this.http.get<SystemStatus>(`${this.base}/status`);
  }

  materials(): Observable<MaterialRow[]> {
    return this.http.get<MaterialRow[]>(`${this.base}/materials`);
  }

  material(id: string): Observable<MaterialView> {
    return this.http.get<MaterialView>(`${this.base}/materials/${encodeURIComponent(id)}`);
  }

  deleteMaterial(id: string): Observable<unknown> {
    return this.http.delete(`${this.base}/materials/${encodeURIComponent(id)}`);
  }

  reprocess(id: string): Observable<unknown> {
    return this.http.post(`${this.base}/materials/${encodeURIComponent(id)}/reprocess`, {});
  }

  label(id: string, ai: boolean): Observable<Record<string, string>> {
    return this.http.post<Record<string, string>>(`${this.base}/materials/${encodeURIComponent(id)}/label`, { ai });
  }

  artifactUrl(id: string, index: number): string {
    return `${this.base}/materials/${encodeURIComponent(id)}/artifacts/${index}`;
  }

  campaigns(): Observable<{ campaigns: Campaign[]; families: Family[] }> {
    return this.http.get<{ campaigns: Campaign[]; families: Family[] }>(`${this.base}/campaigns`);
  }

  graph(minScore = 0.15): Observable<GraphData> {
    return this.http.get<GraphData>(`${this.base}/graph`, { params: { min_score: minScore } });
  }

  compare(a: string, b: string): Observable<PairView> {
    return this.http.get<PairView>(`${this.base}/compare`, { params: { a, b } });
  }

  analyze(files: File[], url: string, label: string): Observable<{ id: string }> {
    const form = new FormData();
    for (const f of files) form.append('files', f, f.name);
    if (url) form.append('url', url);
    if (label) form.append('label', label);
    return this.http.post<{ id: string }>(`${this.base}/analyze`, form);
  }

  importDataset(path?: string): Observable<unknown> {
    return this.http.post(`${this.base}/dataset/import`, path ? { path } : {});
  }

  uploadDataset(file: File): Observable<unknown> {
    const form = new FormData();
    form.append('file', file, file.name);
    return this.http.post(`${this.base}/dataset/upload`, form);
  }

  trainAi(): Observable<Record<string, unknown>> {
    return this.http.post<Record<string, unknown>>(`${this.base}/ai/train`, {});
  }

  reprocessAll(): Observable<{ queued: number }> {
    return this.http.post<{ queued: number }>(`${this.base}/reprocess`, {});
  }

  exportUrl(): string {
    return `${this.base}/export`;
  }
}
