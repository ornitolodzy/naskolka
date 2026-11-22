import { ChangeDetectionStrategy, Component, OnDestroy, inject, signal } from '@angular/core';
import { DecimalPipe, JsonPipe, KeyValuePipe } from '@angular/common';

import { Api } from '../../core/api.service';
import { SystemStatus } from '../../core/models';

@Component({
  selector: 'app-system',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DecimalPipe, JsonPipe, KeyValuePipe],
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
            <span class="lamp-dot" [class]="s.modules.asr.error ? 'lamp-2' : s.modules.asr.enabled && s.modules.asr.installed ? 'lamp-0' : 'lamp-1'"></span>
            Transkrypcja mowy (faster-whisper {{ s.modules.asr.model }}, {{ s.modules.asr.device }})
            @if (s.modules.asr.error) { <span class="muted small">{{ s.modules.asr.error }}</span> }
          </div>
          <div class="row">
            <span class="lamp-dot" [class]="s.modules.clip.error ? 'lamp-2' : s.modules.clip.present ? 'lamp-0' : 'lamp-1'"></span>
            Embeddingi obrazów (CLIP {{ s.modules.clip.key }})
          </div>
          <div class="row">
            <span class="lamp-dot" [class]="s.modules.llm.reachable ? 'lamp-0' : s.modules.llm.configured ? 'lamp-2' : 'lamp-1'"></span>
            LLM (Ollama): {{ s.modules.llm.configured ? s.modules.llm.model : 'nieskonfigurowany, działa słownik' }}
          </div>
          <div class="row"><span class="lamp-dot" [class]="s.modules.online_enrichment ? 'lamp-0' : 'lamp-1'"></span> Wzbogacanie online (RDAP, DNS)</div>
          <div class="small muted">Progi: {{ s.thresholds | json }}</div>
        </section>

        <section class="card stack">
          <h3>Detektor AI</h3>
          <p class="small">
            Uczy się na obrazach, które same deklarują AI (podpis, etykieta platformy, metadane C2PA/IPTC/SynthID),
            na ocenach analityka oraz na korpusie startowym obrazów AI i prawdziwych zdjęć. Lampkę podnosi dopiero
            model, który przejdzie wszystkie progi wiarygodności.
          </p>
          @let d = s.modules.ai_detector;
          @if (d.trained) {
            <table class="tbl small">
              <tbody>
                <tr><td>Cechy / tryb</td><td>{{ d.features }} · {{ d.mode }}</td><td></td></tr>
                <tr>
                  <td>Przykłady AI</td><td>{{ d.positives }} z {{ d.positive_sources }} źródeł</td>
                  <td>{{ ok((d.positives ?? 0) >= d.reliable_requires.positives && (d.positive_sources ?? 0) >= d.reliable_requires.positive_sources) }}</td>
                </tr>
                <tr><td>Przykłady nie-AI</td><td>{{ d.negatives }} (+ {{ d.unlabeled }} nieoznaczonych ze zbioru)</td><td></td></tr>
                <tr>
                  <td>AUC na nowych generatorach</td>
                  <td>{{ d.heldout_auc ?? '-' }} (min {{ d.reliable_requires.heldout_auc }})</td>
                  <td>{{ ok((d.heldout_auc ?? 0) >= d.reliable_requires.heldout_auc) }}</td>
                </tr>
                <tr>
                  <td>Oznaczone obrazy ze zbioru</td>
                  <td>{{ (d.unlabeled_flag_rate ?? 0) * 100 | number: '1.0-0' }}% (max {{ d.reliable_requires.max_unlabeled_flag_rate * 100 }}%)</td>
                  <td>{{ ok(d.unlabeled_flag_rate == null || d.unlabeled_flag_rate <= d.reliable_requires.max_unlabeled_flag_rate) }}</td>
                </tr>
              </tbody>
            </table>
            <div class="notice" [class.warn]="!d.reliable">
              {{ d.reliable ? 'Model wiarygodny: może zapalać czerwoną lampkę.' : 'Model niewiarygodny: wynik jest tylko informacyjny. Najczęstszy powód to brak przykładów nie-AI z tej samej domeny (reklamy, zrzuty stron, klatki wideo). Oznacz kilka materiałów jako „to nie AI”.' }}
            </div>
          } @else {
            <p class="muted small">{{ d.reason || 'Model jeszcze nie był trenowany.' }}</p>
          }
          <div class="small muted">
            Korpus startowy: {{ s.modules.ai_seed.ai }} obrazów AI ({{ s.modules.ai_seed.ai_sources }} generatorów),
            {{ s.modules.ai_seed.real }} prawdziwych ({{ s.modules.ai_seed.real_sources }} źródła)
            @if (s.modules.ai_seed.job.running) { · pobieranie w toku… }
            @if (s.modules.ai_seed.job.error) { · błąd: {{ s.modules.ai_seed.job.error }} }
          </div>
          <div class="row">
            <button class="btn ghost" (click)="seed()" [disabled]="busy() || s.modules.ai_seed.job.running">Pobierz korpus startowy (OpenFake)</button>
            <button class="btn" (click)="train()" [disabled]="busy()">{{ busy() ? 'Trenuję…' : 'Trenuj detektor' }}</button>
          </div>
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
export class SystemPage implements OnDestroy {
  private readonly api = inject(Api);
  protected readonly status = signal<SystemStatus | null>(null);
  protected readonly busy = signal(false);
  protected readonly message = signal<string | null>(null);
  protected readonly exportUrl = this.api.exportUrl();
  private timer?: ReturnType<typeof setTimeout>;

  constructor() {
    this.load();
  }

  ngOnDestroy(): void {
    clearTimeout(this.timer);
  }

  protected ok(v: boolean): string {
    return v ? '✓' : '✗';
  }

  load(): void {
    clearTimeout(this.timer);
    this.api.status().subscribe((s) => {
      this.status.set(s);
      if (s.import.running || s.modules.ai_seed.job.running) {
        this.timer = setTimeout(() => this.load(), 3000);
      }
    });
  }

  train(): void {
    this.busy.set(true);
    this.api.trainAi().subscribe({
      next: () => this.load(),
      complete: () => this.busy.set(false),
      error: () => this.busy.set(false),
    });
  }

  seed(): void {
    this.api.fetchSeed().subscribe(() => {
      this.message.set('Pobieram korpus startowy. Po zakończeniu kliknij „Trenuj detektor”.');
      this.load();
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
