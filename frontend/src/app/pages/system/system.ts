import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { JsonPipe, KeyValuePipe } from '@angular/common';

import { Api } from '../../core/api.service';
import { SystemStatus } from '../../core/models';

@Component({
  selector: 'app-system',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [JsonPipe, KeyValuePipe],
  template: `
    <h1>System</h1>
    @if (status(); as s) {
      <div class="grid cols-2">
        <section class="card stack">
          <h3>Moduły</h3>
          <div class="row"><span class="lamp-dot" [class]="s.modules.ocr ? 'lamp-0' : 'lamp-2'"></span> OCR (RapidOCR)</div>
          <div class="row"><span class="lamp-dot" [class]="s.modules.faces ? 'lamp-0' : 'lamp-2'"></span> Twarze (YuNet + SFace)</div>
          <div class="small muted">
            Galeria osób publicznych:
            @for (g of s.modules.faces_gallery | keyvalue; track g.key) { <span class="chip">{{ g.key }} ({{ g.value }})</span> }
            @empty { brak, dodaj zdjęcia do <code>backend/reference/faces/&lt;slug&gt;/</code> }
          </div>
          <div class="row">
            <span class="lamp-dot" [class]="s.modules.llm.reachable ? 'lamp-0' : s.modules.llm.configured ? 'lamp-2' : 'lamp-1'"></span>
            LLM (Ollama): {{ s.modules.llm.configured ? s.modules.llm.model : 'nieskonfigurowany, działa słownik' }}
          </div>
          <div class="row"><span class="lamp-dot" [class]="s.modules.online_enrichment ? 'lamp-0' : 'lamp-1'"></span> Wzbogacanie online (RDAP, DNS)</div>
          <div class="small muted">Progi: {{ s.thresholds | json }}</div>
        </section>

        <section class="card stack">
          <h3>Detektor AI (samouczący)</h3>
          <p class="small">
            Uczy się na materiałach, które same deklarują AI (etykieta platformy, podpis, metadane C2PA/IPTC/SynthID),
            oraz na ocenach analityka. Brak deklaracji to dane nieoznaczone, a nie negatywne (uczenie PU).
            Lampkę podnosi dopiero model wiarygodny (wystarczająco dużo przykładów z kilku materiałów).
          </p>
          <code class="small">{{ s.modules.ai_detector | json }}</code>
          <div class="row">
            <button class="btn" (click)="train()" [disabled]="busy()">Trenuj detektor na bieżących danych</button>
          </div>
          @if (trainResult()) { <code class="small">{{ trainResult() | json }}</code> }
        </section>

        <section class="card stack">
          <h3>Dane</h3>
          <div class="row">
            <button class="btn" (click)="importRaw()" [disabled]="busy() || s.import.running">Importuj zbiór z data/raw</button>
            <label class="btn ghost">Wgraj zbiór .zip<input type="file" accept=".zip" hidden (change)="uploadZip($event)" /></label>
          </div>
          <div class="row">
            <button class="btn ghost" (click)="reprocessAll()" [disabled]="busy()">Przetwórz wszystko ponownie</button>
            <a class="btn ghost" [href]="exportUrl" download>Eksport wzbogaconego zbioru (JSON)</a>
          </div>
          <div class="small muted">
            Materiałów: {{ s.materials }}
            @if (s.import.running) { · import w toku ({{ s.import.total }} incydentów) }
          </div>
          @if (message()) { <div class="notice">{{ message() }}</div> }
        </section>
      </div>
    }
  `,
})
export class SystemPage {
  private readonly api = inject(Api);
  protected readonly status = signal<SystemStatus | null>(null);
  protected readonly busy = signal(false);
  protected readonly message = signal<string | null>(null);
  protected readonly trainResult = signal<Record<string, unknown> | null>(null);
  protected readonly exportUrl = this.api.exportUrl();

  constructor() {
    this.load();
  }

  load(): void {
    this.api.status().subscribe((s) => this.status.set(s));
  }

  train(): void {
    this.busy.set(true);
    this.api.trainAi().subscribe({
      next: (r) => {
        this.trainResult.set(r);
        this.load();
      },
      complete: () => this.busy.set(false),
      error: () => this.busy.set(false),
    });
  }

  importRaw(): void {
    this.api.importDataset().subscribe(() => {
      this.message.set('Import uruchomiony: postęp widać na stronie Kampanie.');
      this.load();
    });
  }

  uploadZip(e: Event): void {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file) return;
    this.busy.set(true);
    this.message.set(`Wysyłam ${file.name}…`);
    this.api.uploadDataset(file).subscribe({
      next: () => this.message.set('Archiwum rozpakowane, import w toku.'),
      error: (err) => this.message.set(err?.error?.detail ?? 'Błąd wysyłania'),
      complete: () => {
        this.busy.set(false);
        this.load();
      },
    });
  }

  reprocessAll(): void {
    this.api.reprocessAll().subscribe((r) => this.message.set(`W kolejce: ${r.queued} materiałów.`));
  }
}
