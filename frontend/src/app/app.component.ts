import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { NavigationHistoryService } from './core/services/navigation-history.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent {
  // Inject so the service starts tracking navigation from app boot.
  constructor(_history: NavigationHistoryService) {}
}
