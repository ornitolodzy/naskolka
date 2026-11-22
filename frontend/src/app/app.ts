import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <header class="topbar">
      <a routerLink="/" class="brand">
        <svg class="brand-mark" viewBox="0 0 32 32" aria-hidden="true">
          <path d="M4 10.5c6 0 10 2.2 12 6.2 2-4 6-6.2 12-6.2-5 2-8.6 5.2-10.6 10.3h-2.8C12.6 15.7 9 12.5 4 10.5Z" fill="#F4EBE1" />
          <path d="M14.6 20.8h2.8l2.3 6.4-3.7-3.6-3.7 3.6Z" fill="#A33B24" />
        </svg>
        <span class="brand-name">naskółka</span>
        <small>NASK · follow the fake</small>
      </a>
      <nav>
        <a routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{ exact: true }">Kampanie</a>
        <a routerLink="/graf" routerLinkActive="active">Graf</a>
        <a routerLink="/materialy" routerLinkActive="active">Materiały</a>
        <a routerLink="/analiza" routerLinkActive="active" class="cta">+ Nowa analiza</a>
      </nav>
    </header>
    <main class="page"><router-outlet /></main>
    <footer class="footer">HackNation 2026</footer>
  `,
})
export class App {}
