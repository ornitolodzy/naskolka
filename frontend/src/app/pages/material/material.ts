import { ChangeDetectionStrategy, Component, OnDestroy, computed, effect, inject, input, signal } from '@angular/core';
import { DecimalPipe, JsonPipe, KeyValuePipe } from '@angular/common';
import { Router, RouterLink } from '@angular/router';

import { Api } from '../../core/api.service';
import { MANIPULATION_PL, MaterialView, TOPIC_PL } from '../../core/models';
import { LampView } from '../../shared/lamp';
import { PairEvidence } from '../../shared/pair-evidence';

const DECISION_PL: Record<string, string> = {
  known_campaign: 'Znana kampania',
  related: 'Pokrewna kampania / nowy wariant',
  new_pattern: 'Nowy wzorzec',
  duplicate: 'Duplikat (ponowne zgłoszenie)',
};

@Component({
  selector: 'app-material',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, LampView, PairEvidence, DecimalPipe, KeyValuePipe, JsonPipe],
  templateUrl: './material.html',
  styles: `
    .hero { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    @media (max-width: 1000px) { .hero { grid-template-columns: 1fr; } }
    .kv { display: grid; grid-template-columns: 160px 1fr; gap: 4px 12px; font-size: 13.5px; }
    .kv dt { color: var(--naskolka-text-secondary); }
    .kv dd { margin: 0; }
    @media (max-width: 760px) { .kv { grid-template-columns: 1fr; } .kv dd { margin-bottom: 6px; } }
    .decision { font-size: 24px; font-weight: 600; line-height: 1.3; color: var(--naskolka-text-heading); }
    .tok { display: flex; flex-wrap: wrap; gap: 4px; }
    .transcript { max-height: 280px; overflow: auto; display: grid; gap: 2px; padding: 6px 0; }
  `,
})
export class MaterialPage implements OnDestroy {
  private readonly api = inject(Api);
  private readonly router = inject(Router);
  readonly id = input.required<string>();
  protected readonly view = signal<MaterialView | null>(null);
  protected readonly busy = signal(false);
  protected readonly decision = DECISION_PL;
  protected readonly topicPl = TOPIC_PL;
  protected readonly manipPl = MANIPULATION_PL;
  protected readonly f = computed(() => this.view()?.features ?? null);
  protected readonly images = computed(() =>
    (this.view()?.artifacts ?? []).filter((a) => a.kind === 'screenshot' || a.kind === 'page_image').slice(0, 24),
  );
  protected readonly trackerTokens = computed(() => {
    const t = this.f()?.tokens ?? {};
    const keys = ['fb_pixel', 'gtm', 'google_ads', 'conversion_id', 'ga4', 'url_template', 'ad_account_prefix', 'ad_account_tag',
      'landing_id', 'tracker_campaign', 'lp_key', 'utm_campaign', 'adset_name', 'ad_name', 'clickid_shape', 'path_shape',
      'phone_pl', 'email', 'advertiser', 'advertiser_id'];
    return keys.filter((k) => t[k]).map((k) => ({ key: k, values: Object.keys(t[k]) }));
  });
  protected readonly textDomains = computed(() => Object.keys(this.f()?.tokens?.['text_domain'] ?? {}));
  private timer?: ReturnType<typeof setTimeout>;

  constructor() {
    effect(() => this.load(this.id()));
  }

  ngOnDestroy(): void {
    clearTimeout(this.timer);
  }

  load(id: string): void {
    clearTimeout(this.timer);
    this.api.material(id).subscribe((v) => {
      this.view.set(v);
      if (v.status === 'pending' || v.status === 'processing') {
        this.timer = setTimeout(() => this.load(id), 2500);
      }
    });
  }

  artifactUrl(index: number): string {
    return this.api.artifactUrl(this.id(), index);
  }

  label(body: { ai?: boolean; scam?: boolean }): void {
    this.api.label(this.id(), body).subscribe(() => this.load(this.id()));
  }

  reprocess(): void {
    this.busy.set(true);
    this.api.reprocess(this.id()).subscribe(() => {
      this.busy.set(false);
      this.load(this.id());
    });
  }

  remove(): void {
    if (!confirm(`Usunąć materiał ${this.id()}?`)) return;
    this.api.deleteMaterial(this.id()).subscribe(() => this.router.navigate(['/materialy']));
  }

  protected entries(o: Record<string, number> | undefined): [string, number][] {
    return Object.entries(o ?? {});
  }
}
