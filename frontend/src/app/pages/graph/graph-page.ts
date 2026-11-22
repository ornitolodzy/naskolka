import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnDestroy,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import cytoscape, { Core } from 'cytoscape';

import { Api } from '../../core/api.service';
import { GraphData, PairView } from '../../core/models';
import { PairEvidence } from '../../shared/pair-evidence';

const PALETTE = ['#A33B24', '#1D2A44', '#5E7A3A', '#6E2F7E', '#B5762B', '#2F6F6A', '#4A5C9A', '#872F1C', '#6B6B2F', '#5E5A56'];
const LAMP_BORDER = ['#3F7A3A', '#C8961A', '#A33B24', '#6E2F7E', '#0F1626'];

@Component({
  selector: 'app-graph-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, PairEvidence, RouterLink],
  template: `
    <div class="spread">
      <h1>Graf powiązań</h1>
      <label class="row small">
        pokaż powiązania od
        <input type="range" min="0.05" max="0.9" step="0.05" [(ngModel)]="minScore" (change)="load()" />
        <code>{{ minScore.toFixed(2) }}</code>
      </label>
    </div>
    <p class="muted small">
      Węzeł = materiał (kolor = kampania, obwódka = lampka ryzyka). Krawędź = powiązanie: ciągła gruba = ta sama
      kampania (≥ {{ data()?.thresholds?.campaign }}), przerywana = podobna kampania (≥ {{ data()?.thresholds?.family }}),
      cienka szara = słaby ślad. Kliknij krawędź, żeby zobaczyć przesłanki, albo węzeł, żeby otworzyć materiał.
    </p>
    <div class="layout">
      <div #canvas class="canvas card"></div>
      <aside class="card side">
        @if (pair(); as p) {
          <app-pair-evidence [pair]="p" />
        } @else if (node(); as n) {
          <h2>{{ n }}</h2>
          <a class="btn" [routerLink]="['/materialy', n]">Otwórz materiał</a>
        } @else {
          <p class="muted">Wybierz krawędź lub węzeł.</p>
        }
      </aside>
    </div>
  `,
  styles: `
    .layout { display: grid; grid-template-columns: 1fr 420px; gap: 16px; }
    .canvas { height: 72vh; padding: 0; overflow: hidden; }
    .side { max-height: 72vh; overflow: auto; }
    @media (max-width: 1000px) { .layout { grid-template-columns: 1fr; } }
  `,
})
export class GraphPage implements AfterViewInit, OnDestroy {
  private readonly api = inject(Api);
  private readonly router = inject(Router);
  private readonly canvas = viewChild.required<ElementRef<HTMLDivElement>>('canvas');
  private cy?: Core;
  protected minScore = 0.15;
  protected readonly data = signal<GraphData | null>(null);
  protected readonly pair = signal<PairView | null>(null);
  protected readonly node = signal<string | null>(null);

  ngAfterViewInit(): void {
    this.load();
  }

  ngOnDestroy(): void {
    this.cy?.destroy();
  }

  load(): void {
    this.api.graph(this.minScore).subscribe((d) => {
      this.data.set(d);
      this.render(d);
    });
  }

  private render(d: GraphData): void {
    const campaigns = [...new Set(d.nodes.map((n) => n.campaign ?? '-'))].sort();
    const color = (c: string | null) => PALETTE[campaigns.indexOf(c ?? '-') % PALETTE.length];
    this.cy?.destroy();
    this.cy = cytoscape({
      container: this.canvas().nativeElement,
      elements: [
        ...d.nodes.map((n) => ({
          data: {
            id: n.id,
            label: `${n.id}\n${(n.title ?? '').slice(0, 34)}`,
            color: color(n.campaign),
            border: LAMP_BORDER[n.lamp] ?? '#D8CFC5',
          },
        })),
        ...d.edges.map((e) => ({
          data: {
            id: `${e.source}|${e.target}`,
            source: e.source,
            target: e.target,
            score: e.score,
            label: e.score >= d.thresholds.family ? e.score.toFixed(2) : '',
            kind: e.score >= d.thresholds.campaign ? 'strong' : e.score >= d.thresholds.family ? 'family' : 'weak',
          },
        })),
      ],
      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(color)',
            'border-color': 'data(border)',
            'border-width': 5,
            label: 'data(label)',
            'text-wrap': 'wrap',
            'font-size': 10,
            'text-valign': 'bottom',
            'text-margin-y': 6,
            width: 34,
            height: 34,
            color: '#252321',
            'font-family': 'Plus Jakarta Sans, Inter, sans-serif',
          },
        },
        {
          selector: 'edge',
          style: {
            width: 'mapData(score, 0, 1, 1, 9)',
            'line-color': '#5E5A56',
            'curve-style': 'bezier',
            label: 'data(label)',
            'font-size': 9,
            'text-background-color': '#FAF6F0',
            'text-background-opacity': 1,
          },
        },
        { selector: 'edge[kind = "strong"]', style: { 'line-color': '#0F1626' } },
        { selector: 'edge[kind = "family"]', style: { 'line-style': 'dashed', 'line-color': '#A33B24' } },
        { selector: 'edge[kind = "weak"]', style: { opacity: 0.35 } },
        { selector: ':selected', style: { 'overlay-opacity': 0.15, 'overlay-color': '#A33B24' } },
      ],
      layout: { name: 'cose', animate: false, idealEdgeLength: () => 140, nodeRepulsion: () => 9000, randomize: false },
    });
    this.cy.on('tap', 'edge', (evt) => {
      const e = evt.target;
      this.node.set(null);
      this.api.compare(e.data('source'), e.data('target')).subscribe((p) => this.pair.set(p));
    });
    this.cy.on('tap', 'node', (evt) => {
      this.pair.set(null);
      this.node.set(evt.target.id());
    });
    this.cy.on('dbltap', 'node', (evt) => this.router.navigate(['/materialy', evt.target.id()]));
  }
}
