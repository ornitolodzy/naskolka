import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { Api } from '../../core/api.service';

@Component({
  selector: 'app-analyze',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule],
  template: `
    <h1>Nowa analiza</h1>
    <p class="muted">
      Podaj adres reklamy lub strony, albo wgraj materiały: zrzuty ekranu, nagrania, zapisane strony (.html, .mhtml),
      logi ruchu (.har) lub całe archiwum .zip. Materiał zostanie porównany ze wszystkimi wcześniej
      przeanalizowanymi i przypisany do znanej kampanii albo oznaczony jako nowy wzorzec.
    </p>
    <div class="card stack" style="max-width: 820px">
      <label class="field">
        <span>Adres URL (opcjonalnie)</span>
        <input type="url" [(ngModel)]="url" placeholder="https://..." />
      </label>
      <div
        class="drop"
        [class.over]="over()"
        (dragover)="$event.preventDefault(); over.set(true)"
        (dragleave)="over.set(false)"
        (drop)="onDrop($event)"
      >
        <p><strong>Przeciągnij pliki tutaj</strong> albo</p>
        <input type="file" multiple (change)="onPick($event)" />
        @if (files().length) {
          <ul class="small">
            @for (f of files(); track f.name) { <li>{{ f.name }} <span class="muted">({{ (f.size / 1024 / 1024).toFixed(1) }} MB)</span></li> }
          </ul>
        }
      </div>
      <label class="field">
        <span>Etykieta (opcjonalnie)</span>
        <input type="text" [(ngModel)]="label" placeholder="np. reklama z Instagrama 22.11" />
      </label>
      @if (error()) { <div class="notice bad">{{ error() }}</div> }
      <div class="row">
        <button class="btn" (click)="submit()" [disabled]="busy() || (!url && files().length === 0)">
          {{ busy() ? 'Wysyłam…' : 'Analizuj i porównaj' }}
        </button>
        @if (files().length) { <button class="btn ghost" (click)="files.set([])">Wyczyść pliki</button> }
      </div>
    </div>
  `,
  styles: `
    .field { display: grid; gap: 4px; }
    .field span { font-size: 13px; color: var(--naskolka-text-secondary); }
    .field input { padding: 10px 14px; border-radius: var(--radius-sm); border: 1px solid var(--naskolka-border-subtle); background: var(--naskolka-bg-canvas); }
    .field input:focus { border-color: var(--naskolka-accent-primary); outline: none; }
    .drop { border: 2px dashed var(--naskolka-border-subtle); border-radius: var(--radius-md); padding: 18px; text-align: center; background: var(--naskolka-bg-canvas); }
    .drop.over { border-color: var(--naskolka-accent-primary); background: var(--naskolka-accent-tint); }
    .drop ul { text-align: left; }
  `,
})
export class Analyze {
  private readonly api = inject(Api);
  private readonly router = inject(Router);
  protected url = '';
  protected label = '';
  protected readonly files = signal<File[]>([]);
  protected readonly busy = signal(false);
  protected readonly over = signal(false);
  protected readonly error = signal<string | null>(null);

  onPick(e: Event): void {
    const list = (e.target as HTMLInputElement).files;
    if (list) this.files.update((f) => [...f, ...Array.from(list)]);
  }

  onDrop(e: DragEvent): void {
    e.preventDefault();
    this.over.set(false);
    const list = e.dataTransfer?.files;
    if (list) this.files.update((f) => [...f, ...Array.from(list)]);
  }

  submit(): void {
    this.busy.set(true);
    this.error.set(null);
    this.api.analyze(this.files(), this.url.trim(), this.label.trim()).subscribe({
      next: (r) => this.router.navigate(['/materialy', r.id]),
      error: (err) => {
        this.busy.set(false);
        this.error.set(err?.error?.detail ?? 'Nie udało się wysłać materiału.');
      },
    });
  }
}
