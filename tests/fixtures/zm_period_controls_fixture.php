<?php
declare(strict_types=1);
/** Disposable HTTP test fixture ONLY; never deploy this file as production period control.
 * The effective production handler is private period_controls.php on cPanel.
 * A known synthetic locked date ensures app.php actually invokes the guard.
 */
function zmPeriodGuard(PDO $db, string $date): void {
    if (str_starts_with($date, '2026-02-')) {
        bail('دوره مالی بسته است.', 403);
    }
}
