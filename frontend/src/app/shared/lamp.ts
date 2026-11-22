import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { Lamp } from '../core/models';

const NAMES = ['zielona', 'żółta', 'czerwona', 'osoba publiczna', 'manipulacja'];

@Component({
  selector: 'app-lamp',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (lamp(); as l) {
      @if (compact()) {
        <span class="lamp-dot lamp-{{ l.level }}" [title]="l.label + ' - ' + l.reasons.join('; ')"></span>
      } @else {
        <div class="lamp-full">
          <div class="steps">
            @for (n of names; track $index) {
              <span class="step" [class.on]="$index <= l.level" [class.current]="$index === l.level">
                <span class="lamp-dot lamp-{{ $index }}"></span>{{ n }}
              </span>
            }
          </div>
          <div class="label">Poziom {{ l.level }}: {{ l.label }}</div>
          <ul class="reasons">
            @for (r of l.reasons; track r) {
              <li>{{ r }}</li>
            }
          </ul>
          <div class="row small">
            <span class="chip" [class.accent]="l.indicators.ai_declared">AI zadeklarowane: {{ l.indicators.ai_declared ? 'tak' : 'nie' }}</span>
            <span class="chip" [class.accent]="l.indicators.ai_detected">
              detektor AI: {{ score() }}{{ l.indicators.ai_detector_reliable ? '' : ' (w nauce)' }}
            </span>
            <span class="chip" [class.accent]="l.indicators.public_person">osoba publiczna: {{ l.indicators.public_person ? 'tak' : 'nie' }}</span>
            <span class="chip" [class.accent]="l.indicators.manipulative">manipulacja: {{ l.indicators.manipulation_score.toFixed(2) }}</span>
          </div>
        </div>
      }
    } @else {
      <span class="muted small">brak danych</span>
    }
  `,
  styles: `
    .steps { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
    .step { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px;
      border: 1px solid var(--fk-line); font-size: 12.5px; opacity: 0.45; }
    .step.on { opacity: 1; }
    .step.current { border-color: var(--fk-ink); font-weight: 700; background: var(--fk-surface-2); }
    .label { font-weight: 700; font-size: 17px; }
    .reasons { margin: 6px 0 10px; padding-left: 18px; color: var(--fk-ink-soft); }
  `,
})
export class LampView {
  readonly lamp = input<Lamp | null>(null);
  readonly compact = input(false);
  protected readonly names = NAMES;
  protected readonly score = computed(() => {
    const s = this.lamp()?.indicators.ai_score;
    return s === null || s === undefined ? 'brak modelu' : s.toFixed(2);
  });
}
