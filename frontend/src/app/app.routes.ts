import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', loadComponent: () => import('./pages/dashboard/dashboard').then((m) => m.Dashboard), title: 'Kampanie' },
  { path: 'graf', loadComponent: () => import('./pages/graph/graph-page').then((m) => m.GraphPage), title: 'Graf powiązań' },
  { path: 'materialy', loadComponent: () => import('./pages/materials/materials').then((m) => m.Materials), title: 'Materiały' },
  {
    path: 'materialy/:id',
    loadComponent: () => import('./pages/material/material').then((m) => m.MaterialPage),
    title: 'Materiał',
  },
  { path: 'analiza', loadComponent: () => import('./pages/analyze/analyze').then((m) => m.Analyze), title: 'Nowa analiza' },
  { path: 'system', loadComponent: () => import('./pages/system/system').then((m) => m.SystemPage), title: 'System' },
  { path: '**', redirectTo: '' },
];
