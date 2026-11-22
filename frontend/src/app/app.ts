import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <header class="topbar">
      <a routerLink="/" class="brand">
        <span class="brand-mark" aria-hidden="true">◉</span>
        <span>Kolekcjoner fejków</span>
        <small>follow the fake</small>
      </a>
      <nav>
        <a routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{ exact: true }">Kampanie</a>
        <a routerLink="/graf" routerLinkActive="active">Graf</a>
        <a routerLink="/materialy" routerLinkActive="active">Materiały</a>
        <a routerLink="/analiza" routerLinkActive="active" class="cta">+ Nowa analiza</a>
        <a routerLink="/system" routerLinkActive="active">System</a>
      </nav>
    </header>
    <main class="page"><router-outlet /></main>
  `,
})
export class App {}
