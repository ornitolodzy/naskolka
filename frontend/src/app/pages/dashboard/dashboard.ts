import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { RouterLink } from '@angular/router';

import { Api } from '../../core/api.service';
import { Campaign, Family, MaterialRow } from '../../core/models';
import { LampView } from '../../shared/lamp';

@Component({
  selector: 'app-dashboard',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, LampView, DecimalPipe],
  template: `
    <div class="spread">
      <h1>Kampanie</h1>
      <div class="row">
        <button class="btn ghost" (click)="load()">Odśwież</button>
        <a class="btn" routerLink="/analiza">+ Analizuj nowy materiał</a>
      </div>
    </div>

    <div class="grid cols-4" style="margin: 12px 0 22px">
      <div class="card"><div class="stat">{{ materials().length }}</div><div class="stat-label">materiałów</div></div>
      <div class="card"><div class="stat">{{ multi().length }}</div><div class="stat-label">kampanii (≥ 2 materiały)</div></div>
      <div class="card"><div class="stat">{{ singles().length }}</div><div class="stat-label">pojedyncze wzorce</div></div>
      <div class="card"><div class="stat">{{ families().length }}</div><div class="stat-label">rodziny kampanii</div></div>
      <div class="card"><div class="stat">{{ redLamps() }}</div><div class="stat-label">w znanych kampaniach oszustw</div></div>
      <div class="card"><div class="stat">{{ orangeLamps() }}</div><div class="stat-label">wysokie ryzyko, nowe wzorce</div></div>
    </div>

    @if (!loading() && materials().length === 0) {
      <div class="card stack">
        <h2>Brak materiałów</h2>
        <p>Zaimportuj udostępniony zbiór (folder <code>data/raw</code>) albo przeanalizuj pojedynczy materiał.</p>
        <div class="row">
          <button class="btn" (click)="importDataset()" [disabled]="importing()">Importuj zbiór z data/raw</button>
          <a class="btn ghost" routerLink="/system">Wgraj archiwum .zip</a>
        </div>
      </div>
    }
    @if (pending() > 0) {
      <div class="notice warn" style="margin-bottom: 16px">Przetwarzanie: {{ pending() }} materiał(ów) w kolejce, odświeżam automatycznie…</div>
    }

    <div class="grid cols-2">
      @for (c of campaigns(); track c.id) {
        <section class="card stack campaign" [class.single]="c.size === 1">
          <div class="spread">
            <div class="row">
              <span class="chip strong">{{ c.id }}</span>
              <app-lamp [lamp]="c.max_lamp" [compact]="true" />
              <strong>{{ c.name }}</strong>
            </div>
            <span class="muted small">
              {{ c.size }} mat.
              @if (c.cohesion !== null) { · spójność {{ c.cohesion | number: '1.2-2' }} }
              @if (c.family) { · rodzina {{ c.family }} }
            </span>
          </div>
          <div class="row">
            @for (m of c.members; track m) {
              <a class="chip" [routerLink]="['/materialy', m]" [title]="c.titles[m] || ''">{{ m }}</a>
            }
          </div>
          @if (c.domains.length) {
            <div class="small"><span class="muted">domeny:</span> <code>{{ c.domains.join(', ') }}</code></div>
          }
          @if (c.persons.length) {
            <div class="row small">
              <span class="muted">osoby:</span>
              @for (p of c.persons; track p.slug) { <span class="chip accent">{{ p.name }}</span> }
            </div>
          }
          <div>
            <h3>{{ c.size > 1 ? 'Wspólne ślady (sygnatura kampanii)' : 'Charakterystyczne ślady' }}</h3>
            <ul class="sig">
              @for (s of c.signature.slice(0, 6); track $index) {
                <li>
                  <span class="muted small">{{ s.label }}</span>
                  <code>{{ s.value }}</code>
                  @if (c.size > 1) { <span class="chip">{{ s.members }}/{{ c.size }}</span> }
                </li>
              }
            </ul>
          </div>
        </section>
      }
    </div>

    @if (families().length) {
      <h2 style="margin-top: 28px">Rodziny podobnych kampanii</h2>
      <div class="grid cols-3">
        @for (f of families(); track f.id) {
          <div class="card">
            <div class="row"><span class="chip strong">{{ f.id }}</span> {{ f.campaigns.join(' · ') }}</div>
            <ul class="small">
              @for (l of f.links; track $index) {
                <li>{{ l.a }} ↔ {{ l.b }}: najsilniejsze powiązanie {{ l.score | number: '1.2-2' }}</li>
              }
            </ul>
          </div>
        }
      </div>
    }
  `,
  styles: `
    .campaign.single { opacity: 0.85; }
    .sig { list-style: none; padding: 0; margin: 0; display: grid; gap: 4px; }
    .sig li { display: grid; grid-template-columns: 1fr auto; gap: 2px 10px; }
    .sig li .muted { grid-column: 1 / -1; }
  `,
})
export class Dashboard {
  private readonly api = inject(Api);
  protected readonly campaigns = signal<Campaign[]>([]);
  protected readonly families = signal<Family[]>([]);
  protected readonly materials = signal<MaterialRow[]>([]);
  protected readonly loading = signal(true);
  protected readonly importing = signal(false);
  protected readonly multi = computed(() => this.campaigns().filter((c) => c.size > 1));
  protected readonly singles = computed(() => this.campaigns().filter((c) => c.size === 1));
  protected readonly redLamps = computed(() => this.materials().filter((m) => m.lamp?.level === 3).length);
  protected readonly orangeLamps = computed(() => this.materials().filter((m) => m.lamp?.level === 2).length);
  protected readonly pending = computed(() => this.materials().filter((m) => m.status === 'pending' || m.status === 'processing').length);
  private timer?: ReturnType<typeof setTimeout>;

  constructor() {
    this.load();
  }

  load(): void {
    this.api.materials().subscribe((m) => {
      this.materials.set(m);
      this.loading.set(false);
      clearTimeout(this.timer);
      if (this.pending() > 0) this.timer = setTimeout(() => this.load(), 3000);
    });
    this.api.campaigns().subscribe((c) => {
      this.campaigns.set(c.campaigns);
      this.families.set(c.families);
    });
  }

  importDataset(): void {
    this.importing.set(true);
    this.api.importDataset().subscribe({
      next: () => setTimeout(() => this.load(), 1000),
      complete: () => this.importing.set(false),
      error: () => this.importing.set(false),
    });
  }
}
