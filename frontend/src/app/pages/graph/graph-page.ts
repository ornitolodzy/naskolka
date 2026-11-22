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

const PALETTE = ['#6e3b2b', '#2f6f8f', '#7a8f2f', '#8f2f6f', '#b5762b', '#2f8f6a', '#5b4fa3', '#a33f3f', '#3f5aa3', '#6b6b2f'];
const LAMP_BORDER = ['#3f7a3a', '#d9a514', '#e07a10', '#c0392b'];

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
    .canvas { height: 72vh; padding: 0; }
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
            border: LAMP_BORDER[n.lamp] ?? '#999',
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
            color: '#1f1e1e',
          },
        },
        {
          selector: 'edge',
          style: {
            width: 'mapData(score, 0, 1, 1, 9)',
            'line-color': '#8f8378',
            'curve-style': 'bezier',
            label: 'data(label)',
            'font-size': 9,
            'text-background-color': '#f7f4ee',
            'text-background-opacity': 1,
          },
        },
        { selector: 'edge[kind = "strong"]', style: { 'line-color': '#1f1e1e' } },
        { selector: 'edge[kind = "family"]', style: { 'line-style': 'dashed', 'line-color': '#6e3b2b' } },
        { selector: 'edge[kind = "weak"]', style: { opacity: 0.35 } },
        { selector: ':selected', style: { 'overlay-opacity': 0.15, 'overlay-color': '#c0392b' } },
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
