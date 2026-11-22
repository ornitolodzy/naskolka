import { ActivatedRouteSnapshot, ViewTransitionInfo } from '@angular/router';

/** Kolejność zakładek w banerze (od lewej). Trasy spoza menu dostają indeks za ostatnią zakładką. */
export const NAV_ORDER = ['', 'graf', 'materialy', 'analiza'];
/** Zakładka otwierana jak arkusz od dołu, a nie w karuzeli. */
const SHEET = NAV_ORDER.indexOf('analiza');

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
 * Wyjątek: „Nowa analiza” wjeżdża od dołu i chowa się w dół.
 */
export function onNavTransition({ transition, from, to }: ViewTransitionInfo): void {
  const a = navIndex(from);
  const b = navIndex(to);
  let dir: string;
  if (a === b && a === SHEET) dir = 'none';
  else if (b === SHEET) dir = 'up'; // „Nowa analiza” wysuwa się od dołu
  else if (a === SHEET) dir = 'down'; // …i chowa w dół przy wyjściu
  else dir = b !== a ? (b > a ? 'next' : 'prev') : depth(to) >= depth(from) ? 'next' : 'prev';
  const root = document.documentElement;
  root.dataset['navDir'] = dir;
  transition.finished.finally(() => {
    if (root.dataset['navDir'] === dir) delete root.dataset['navDir'];
  });
}
