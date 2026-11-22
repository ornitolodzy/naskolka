import { ActivatedRouteSnapshot, ViewTransitionInfo } from '@angular/router';

/** Kolejność zakładek w banerze (od lewej). Trasy spoza menu dostają indeks za ostatnią zakładką. */
const NAV_ORDER = ['', 'graf', 'materialy', 'analiza'];

function navIndex(route: ActivatedRouteSnapshot): number {
  let r = route;
  while (r.firstChild) r = r.firstChild;
  const top = r.pathFromRoot.flatMap((s) => s.url.map((u) => u.path))[0] ?? '';
  const i = NAV_ORDER.indexOf(top);
  return i === -1 ? NAV_ORDER.length : i;
}

function depth(route: ActivatedRouteSnapshot): number {
  let r = route;
  while (r.firstChild) r = r.firstChild;
  return r.pathFromRoot.reduce((n, s) => n + s.url.length, 0);
}

/**
 * Karuzela: dolna część strony wjeżdża z prawej, gdy przechodzimy do zakładki
 * leżącej dalej w banerze, a z lewej, gdy wracamy do wcześniejszej.
 */
export function onNavTransition({ transition, from, to }: ViewTransitionInfo): void {
  const a = navIndex(from);
  const b = navIndex(to);
  const dir = b !== a ? (b > a ? 'next' : 'prev') : depth(to) >= depth(from) ? 'next' : 'prev';
  const root = document.documentElement;
  root.dataset['navDir'] = dir;
  transition.finished.finally(() => {
    if (root.dataset['navDir'] === dir) delete root.dataset['navDir'];
  });
}
