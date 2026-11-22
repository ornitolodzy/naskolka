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
      <label
        class="drop"
        [class.over]="over()"
        (dragenter)="$event.preventDefault(); over.set(true)"
        (dragover)="$event.preventDefault(); over.set(true)"
        (dragleave)="onLeave($event)"
        (drop)="onDrop($event)"
      >
        <input class="drop-input" type="file" multiple (change)="onPick($event)" />
        <span class="drop-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 15V4" />
            <path d="m7 9 5-5 5 5" />
            <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
          </svg>
        </span>
        <span class="drop-title">{{ over() ? 'Upuść, aby dodać' : 'Kliknij lub przeciągnij pliki' }}</span>
        <span class="drop-hint">Zrzuty ekranu, nagrania, .html / .mhtml, .har lub archiwum .zip</span>
      </label>
      @if (files().length) {
        <ul class="files">
          @for (f of files(); track $index) {
            <li>
              <span class="file-ext">{{ ext(f.name) }}</span>
              <span class="file-name" [title]="f.name">{{ f.name }}</span>
              <span class="file-size">{{ size(f.size) }}</span>
              <button type="button" class="file-remove" (click)="removeFile($index)" [attr.aria-label]="'Usuń ' + f.name">×</button>
            </li>
          }
        </ul>
      }
      <label class="field">
        <span>Etykieta (opcjonalnie)</span>
        <input type="text" [(ngModel)]="label" placeholder="np. reklama z Instagrama 22.11" />
      </label>
      @if (error()) { <div class="notice bad">{{ error() }}</div> }
      <div class="row actions">
        <button class="btn submit" (click)="submit()" [disabled]="busy() || (!url && files().length === 0)">
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
    @media (max-width: 760px) {
      .actions { flex-direction: column; align-items: stretch; }
      .actions .btn { justify-content: center; width: 100%; padding: 14px 18px; font-size: 15px; }
    }
    .drop {
      position: relative; display: flex; flex-direction: column; align-items: center; gap: 6px;
      padding: 28px 18px; text-align: center; cursor: pointer;
      border: 2px dashed var(--naskolka-border-subtle); border-radius: var(--radius-md);
      background: var(--naskolka-bg-canvas);
      transition: border-color 0.2s ease, background-color 0.2s ease;
    }
    .drop:hover { border-color: var(--naskolka-text-secondary); }
    .drop.over { border-color: var(--naskolka-accent-primary); background: var(--naskolka-accent-tint); }
    .drop:focus-within { border-color: var(--naskolka-accent-primary); }
    .drop-input { position: absolute; width: 1px; height: 1px; opacity: 0; overflow: hidden; pointer-events: none; }
    .drop-icon {
      display: grid; place-items: center; width: 48px; height: 48px; margin-bottom: 4px;
      border-radius: var(--radius-sm); background: var(--naskolka-bg-surface);
      border: 1px solid var(--naskolka-border-subtle); color: var(--naskolka-accent-primary);
      transition: transform 0.2s ease;
    }
    .drop-icon svg { width: 24px; height: 24px; }
    .drop:hover .drop-icon, .drop.over .drop-icon { transform: translateY(-3px); }
    .drop-title { font-size: 15px; font-weight: 600; color: var(--naskolka-text-heading); }
    .drop-hint { font-size: 12.5px; line-height: 1.4; color: var(--naskolka-text-secondary); }
    .drop * { pointer-events: none; }
    .files { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
    .files li {
      display: grid; grid-template-columns: auto 1fr auto auto; align-items: center; gap: 10px;
      padding: 6px 6px 6px 8px; border-radius: var(--radius-sm);
      background: var(--naskolka-bg-canvas); border: 1px solid var(--naskolka-border-subtle); font-size: 13.5px;
    }
    .file-ext {
      min-width: 44px; padding: 2px 6px; border-radius: var(--radius-xs); text-align: center;
      font-family: var(--font-mono); font-size: 11px; text-transform: uppercase;
      background: var(--naskolka-navy-black); color: var(--naskolka-text-on-dark);
    }
    .file-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .file-size { font-family: var(--font-mono); font-size: 12px; color: var(--naskolka-text-secondary); }
    .file-remove {
      width: 28px; height: 28px; border: none; border-radius: var(--radius-xs); cursor: pointer;
      background: transparent; color: var(--naskolka-text-secondary); font-size: 18px; line-height: 1;
    }
    .file-remove:hover { background: var(--naskolka-accent-tint); color: var(--naskolka-accent-primary); }
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
    const input = e.target as HTMLInputElement;
    if (input.files) this.files.update((f) => [...f, ...Array.from(input.files!)]);
    input.value = '';
  }

  onLeave(e: DragEvent): void {
    const el = e.currentTarget as HTMLElement;
    if (!el.contains(e.relatedTarget as Node | null)) this.over.set(false);
  }

  removeFile(i: number): void {
    this.files.update((f) => f.filter((_, j) => j !== i));
  }

  ext(name: string): string {
    const i = name.lastIndexOf('.');
    return i > 0 ? name.slice(i + 1, i + 6) : 'plik';
  }

  size(bytes: number): string {
    if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
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
