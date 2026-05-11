import { Injectable } from '@angular/core';
import { Location } from '@angular/common';
import { NavigationEnd, Router, UrlTree } from '@angular/router';

@Injectable({ providedIn: 'root' })
export class NavigationHistoryService {
  private inAppNavigations = 0;

  constructor(private router: Router, private location: Location) {
    router.events.subscribe((e) => {
      if (e instanceof NavigationEnd) this.inAppNavigations++;
    });
  }

  /**
   * Pop the previous in-app history entry (preserving its query params).
   * Falls back to navigating to `fallback` when the current entry is the
   * first one in this tab (e.g. user opened a deep link).
   */
  back(fallback: any[] | UrlTree | string, extras?: { queryParams?: any }): void {
    if (this.inAppNavigations > 1) {
      this.location.back();
      return;
    }
    if (typeof fallback === 'string' || fallback instanceof UrlTree) {
      this.router.navigateByUrl(fallback as any);
    } else {
      this.router.navigate(fallback, extras);
    }
  }
}
