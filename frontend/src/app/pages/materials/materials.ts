import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Api } from '../../core/api.service';
import { MaterialRow, TOPIC_PL } from '../../core/models';
import { LampView } from '../../shared/lamp';

@Component({
  selector: 'app-materials',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, LampView],
  template: `
    <div class="spread">
      <h1>Materiały</h1>
      <button class="btn ghost" (click)="load()">Odśwież</button>
    </div>
    <div class="card">
      <table class="tbl">
        <thead>
          <tr>
            <th></th><th>Materiał</th><th>Tytuł / narracja</th><th>Kampania</th><th>Domeny</th><th>Osoby</th><th>Dane</th><th>Status</th>
          </tr>
        </thead>
        <tbody>
          @for (m of rows(); track m.id) {
            <tr>
              <td><app-lamp [lamp]="m.lamp" [compact]="true" /></td>
              <td>
                <a [routerLink]="['/materialy', m.id]"><strong>{{ m.id }}</strong></a>
                <div class="muted small">{{ m.source }}</div>
              </td>
              <td>
                {{ m.title }}
                @if (m.topic) { <div class="muted small">{{ topic[m.topic] || m.topic }}</div> }
              </td>
              <td>@if (m.campaign) { <span class="chip strong">{{ m.campaign }}</span> }</td>
              <td><code>{{ m.domains.join(', ') }}</code></td>
              <td class="small">{{ m.persons.join(', ') }}</td>
              <td>
                @if (m.completeness !== null) {
                  <div class="bar" [title]="'kompletność danych ' + m.completeness"><span [style.width.%]="m.completeness * 100"></span></div>
                }
              </td>
              <td class="small">{{ m.status }} @if (m.error) { <span class="muted">{{ m.error }}</span> }</td>
            </tr>
          }
        </tbody>
      </table>
    </div>
  `,
})
export class Materials {
  private readonly api = inject(Api);
  protected readonly rows = signal<MaterialRow[]>([]);
  protected readonly topic = TOPIC_PL;

  constructor() {
    this.load();
  }

  load(): void {
    this.api.materials().subscribe((r) => this.rows.set(r));
  }
}
