import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter, map } from 'rxjs';

import { NAV_ORDER } from './core/nav-transition';

/** Zakładki, między którymi przełącza swipe na telefonie (bez „Nowej analizy”). */
const SWIPE_TABS = NAV_ORDER.filter((p) => p !== 'analiza');
const SWIPE_MIN_X = 70;
const SWIPE_MAX_MS = 700;

@Component({
  selector: 'app-root',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <header class="topbar" [class.open]="menuOpen()">
      <div class="topbar-row">
        <a routerLink="/" class="brand">
          <svg class="brand-mark" viewBox="0 0 32 32" aria-hidden="true">
            <path d="M4 10.5c6 0 10 2.2 12 6.2 2-4 6-6.2 12-6.2-5 2-8.6 5.2-10.6 10.3h-2.8C12.6 15.7 9 12.5 4 10.5Z" fill="#F4EBE1" />
            <path d="M14.6 20.8h2.8l2.3 6.4-3.7-3.6-3.7 3.6Z" fill="#A33B24" />
          </svg>
          <span class="brand-name">naskółka</span>
          <small>NASK · follow the fake</small>
        </a>
        <nav id="main-nav" class="nav">
          <a routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{ exact: true }">Kampanie</a>
          <a routerLink="/graf" routerLinkActive="active">Graf</a>
          <a routerLink="/materialy" routerLinkActive="active">Materiały</a>
          <a routerLink="/analiza" routerLinkActive="active" class="cta">+ Nowa analiza</a>
        </nav>
      </div>
      <button
        type="button"
        class="menu-toggle"
        (click)="menuOpen.set(!menuOpen())"
        [attr.aria-expanded]="menuOpen()"
        aria-controls="main-nav"
        [attr.aria-label]="menuOpen() ? 'Zwiń menu' : 'Rozwiń menu'"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>
    </header>

    <main class="page" (touchstart)="onTouchStart($event)" (touchend)="onTouchEnd($event)">
      <router-outlet />
    </main>

    @if (!onAnalyze()) {
      <a routerLink="/analiza" class="fab" aria-label="Nowa analiza">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true">
          <path d="M12 5v14M5 12h14" />
        </svg>
        <span>Nowa analiza</span>
      </a>
    }
    <footer class="footer">HackNation 2026</footer>
  `,
})
export class App {
  private readonly router = inject(Router);
  protected readonly menuOpen = signal(false);

  private readonly url = toSignal(
    this.router.events.pipe(
      filter((e): e is NavigationEnd => e instanceof NavigationEnd),
      map((e) => {
        this.menuOpen.set(false);
        return e.urlAfterRedirects;
      }),
    ),
    { initialValue: this.router.url },
  );

  protected onAnalyze(): boolean {
    return this.topSegment() === 'analiza';
  }

  private topSegment(): string {
    return this.url().split(/[?#]/)[0].split('/').filter(Boolean)[0] ?? '';
  }

  private isTabRoot(): boolean {
    return this.url().split(/[?#]/)[0].split('/').filter(Boolean).length <= 1;
  }

  // --- Swipe lewo/prawo między zakładkami (tylko ekrany dotykowe) ---
  private touch: { x: number; y: number; t: number } | null = null;

  onTouchStart(e: TouchEvent): void {
    if (e.touches.length !== 1 || this.blocksSwipe(e.target as Element)) {
      this.touch = null;
      return;
    }
    const p = e.touches[0];
    this.touch = { x: p.clientX, y: p.clientY, t: Date.now() };
  }

  onTouchEnd(e: TouchEvent): void {
    const start = this.touch;
    this.touch = null;
    if (!start || e.changedTouches.length !== 1) return;
    const p = e.changedTouches[0];
    const dx = p.clientX - start.x;
    const dy = p.clientY - start.y;
    if (Math.abs(dx) < SWIPE_MIN_X || Math.abs(dx) < Math.abs(dy) * 1.5 || Date.now() - start.t > SWIPE_MAX_MS) return;

    const i = SWIPE_TABS.indexOf(this.topSegment());
    if (i === -1 || !this.isTabRoot()) return;
    const next = i + (dx < 0 ? 1 : -1);
    if (next < 0 || next >= SWIPE_TABS.length) return;
    this.router.navigateByUrl('/' + SWIPE_TABS[next]);
  }

  /** Nie przechwytujemy gestów na grafie, polach formularzy ani elementach przewijanych poziomo. */
  private blocksSwipe(target: Element | null): boolean {
    for (let el = target; el && el !== document.body; el = el.parentElement) {
      if (el.matches('input, textarea, select, .canvas, [data-no-swipe]')) return true;
      if (el.scrollWidth > el.clientWidth + 1) {
        const ox = getComputedStyle(el).overflowX;
        if (ox === 'auto' || ox === 'scroll') return true;
      }
    }
    return false;
  }
}
