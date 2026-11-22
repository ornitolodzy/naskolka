import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { Lamp } from '../core/models';

const STEPS = [
  { name: 'zielona', hint: 'brak sygnałów oszustwa' },
  { name: 'żółta', hint: 'podejrzany' },
  { name: 'pomarańczowa', hint: 'wysokie ryzyko, nowy wzorzec' },
  { name: 'czerwona', hint: 'znana kampania oszustw' },
];

const AI_PL: Record<string, string> = {
  declared: 'AI zadeklarowane',
  detected: 'AI wykryte bez deklaracji',
  possible: 'możliwe AI (detektor w nauce)',
  none: 'brak sygnału AI',
};

@Component({
  selector: 'app-lamp',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (lamp(); as l) {
      @if (compact()) {
        <span class="lamp-dot lamp-{{ l.level }}" [title]="tooltip()"></span>
        @if (l.indicators.ai_status === 'declared' || l.indicators.ai_status === 'detected') {
          <span class="mini" title="{{ l.ai?.text }}">AI</span>
        }
        @if (l.indicators.public_person_strong) {
          <span class="mini" title="{{ l.indicators.public_persons?.join(', ') }}">twarz</span>
        }
      } @else {
        <div class="lamp-full">
          <div class="steps">
            @for (s of steps; track $index) {
              <span class="step" [class.on]="$index === l.level" [title]="s.hint">
                <span class="lamp-dot lamp-{{ $index }}"></span>{{ s.name }}
              </span>
            }
          </div>
          <div class="label">{{ l.label }}</div>
          <ul class="reasons">
            @for (r of l.reasons; track r) {
              <li>{{ r }}</li>
            }
          </ul>

          <div class="row small attrs">
            <span class="chip" [class.accent]="l.indicators.ai_status === 'declared' || l.indicators.ai_status === 'detected'"
                  [title]="l.ai?.text ?? ''">{{ aiLabel() }}</span>
            <span class="chip" [class.accent]="l.indicators.public_person">
              osoba publiczna: {{ l.indicators.public_persons?.length ? l.indicators.public_persons?.join(', ') : 'nie' }}
              {{ l.indicators.public_person_strong ? '(twarz)' : '' }}
            </span>
            <span class="chip" [class.accent]="l.indicators.manipulative">manipulacja: {{ l.indicators.manipulation_score.toFixed(2) }}</span>
            @if (l.indicators.known_campaign) {
              <span class="chip accent">kampania {{ l.indicators.known_campaign }}</span>
            }
            @if (l.indicators.duplicates?.length) {
              <span class="chip">duplikat: {{ l.indicators.duplicates?.join(', ') }}</span>
            }
          </div>

          @if (l.scam; as s) {
            <details class="scam-box scam-{{ s.level }}" [open]="s.level !== 'low'">
              <summary>
                <span>Ryzyko oszustwa: <b>{{ s.label }}</b> ({{ (s.score * 100).toFixed(0) }}%)</span>
                <span class="muted small">{{ s.factors.length }} czynników</span>
              </summary>
              <div class="scam-bar"><span [style.width.%]="s.score * 100"></span></div>
              @if (s.factors.length) {
                <ul class="scam-factors">
                  @for (f of s.factors; track f.key) {
                    <li><b>{{ f.label }}</b>&nbsp;<span class="muted">(+{{ f.weight.toFixed(2) }})</span>: {{ f.detail }}</li>
                  }
                </ul>
              } @else {
                <div class="small muted">Brak czynników typowych dla oszustwa.</div>
              }
              <div class="small muted">Czynniki łączone metodą noisy-OR: ryzyko = 1 − ∏(1 − wᵢ).</div>
            </details>
          }
        </div>
      }
    } @else {
      <span class="muted small">brak danych</span>
    }
  `,
  styles: `
    .steps { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
    .step { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px;
      border: 1px solid var(--fk-line); font-size: 12.5px; opacity: 0.4; }
    .step.on { opacity: 1; border-color: var(--fk-ink); font-weight: 700; background: var(--fk-surface-2); }
    .label { font-weight: 700; font-size: 17px; }
    .reasons { margin: 6px 0 10px; padding-left: 18px; color: var(--fk-ink-soft); }
    .attrs { margin-bottom: 10px; }
    .mini { margin-left: 4px; font-size: 10.5px; padding: 0 5px; border-radius: 4px; border: 1px solid var(--fk-line);
      color: var(--fk-ink-soft); }
    .scam-box { border: 1px solid var(--fk-line); border-left-width: 5px; border-radius: 8px; padding: 8px 12px;
      background: var(--fk-surface-2); }
    .scam-box summary { display: flex; justify-content: space-between; cursor: pointer; font-size: 14.5px; }
    .scam-box.scam-high { border-left-color: var(--fk-lamp-red); }
    .scam-box.scam-elevated { border-left-color: var(--fk-lamp-orange); }
    .scam-box.scam-low { border-left-color: var(--fk-lamp-green); }
    .scam-bar { height: 6px; border-radius: 3px; background: var(--fk-line); margin: 8px 0; overflow: hidden; }
    .scam-bar span { display: block; height: 100%; }
    .scam-high .scam-bar span { background: var(--fk-lamp-red); }
    .scam-elevated .scam-bar span { background: var(--fk-lamp-orange); }
    .scam-low .scam-bar span { background: var(--fk-lamp-green); }
    .scam-factors { margin: 0 0 6px; padding-left: 18px; }
  `,
})
export class LampView {
  readonly lamp = input<Lamp | null>(null);
  readonly compact = input(false);
  protected readonly steps = STEPS;
  protected readonly aiLabel = computed(() => {
    const l = this.lamp();
    return l ? AI_PL[l.indicators.ai_status ?? 'none'] ?? 'brak sygnału AI' : '';
  });
  protected readonly tooltip = computed(() => {
    const l = this.lamp();
    if (!l) return '';
    return [l.label, ...l.reasons].join('\n');
  });
}
