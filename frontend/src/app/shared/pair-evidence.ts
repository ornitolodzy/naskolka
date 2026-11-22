import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { DecimalPipe, KeyValuePipe } from '@angular/common';
import { RouterLink } from '@angular/router';

import { PairView, RELATION_PL } from '../core/models';

@Component({
  selector: 'app-pair-evidence',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DecimalPipe, KeyValuePipe, RouterLink],
  template: `
    @let p = pair();
    <div class="spread">
      <div class="row">
        <a [routerLink]="['/materialy', p.a]" class="chip">{{ p.a }}</a>
        <span>↔</span>
        <a [routerLink]="['/materialy', p.b]" class="chip">{{ p.b }}</a>
        <span class="chip" [class.strong]="p.relation === 'variant' || p.relation === 'duplicate'">{{ relation[p.relation] }}</span>
      </div>
      <strong class="mono">wynik {{ p.score | number: '1.2-2' }}</strong>
    </div>
    <div class="channels">
      @for (c of p.channels | keyvalue: byValue; track c.key) {
        <div class="ch-row">
          <span class="small">{{ c.key }}</span>
          <div class="bar"><span [style.width.%]="c.value * 100"></span></div>
          <span class="mono small">{{ c.value | number: '1.2-2' }}</span>
        </div>
      }
    </div>
    <ul class="evidence">
      @for (e of p.evidence; track $index) {
        <li>
          <span class="ch">{{ e.channel }}</span>
          <span><strong>{{ e.value }}</strong><br /><span class="muted small">{{ e.detail }}</span></span>
          <span class="w">{{ e.weight | number: '1.2-2' }}</span>
        </li>
      }
    </ul>
    @if (p.evidence_total > p.evidence.length) {
      <div class="muted small">+ {{ p.evidence_total - p.evidence.length }} słabszych przesłanek</div>
    }
  `,
  styles: `
    .channels { margin: 10px 0; display: grid; gap: 4px; }
    .ch-row { display: grid; grid-template-columns: 120px 1fr 44px; gap: 8px; align-items: center; }
  `,
})
export class PairEvidence {
  readonly pair = input.required<PairView>();
  protected readonly relation = RELATION_PL;
  protected byValue = (a: { value: number }, b: { value: number }) => b.value - a.value;
}
