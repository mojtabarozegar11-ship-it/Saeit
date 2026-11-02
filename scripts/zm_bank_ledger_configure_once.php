<?php
declare(strict_types=1);
/**
 * Explicit one-time owner-authorized bookkeeping chart setup.
 * It creates two bank ledger labels and an evidence registry, never a payment.
 * It is CLI only and accepts no bank numbers, transaction data, or credentials.
 */
ini_set('display_errors', 'stderr');
if (PHP_SAPI !== 'cli' || count($argv) !== 3) {
    fwrite(STDERR, "Usage: php zm_bank_ledger_configure_once.php PRIVATE_ROOT 40_HEX_REVISION\n");
    exit(64);
}

[$unused, $rootArg, $revision] = $argv;
if (!preg_match('/\A[a-f0-9]{40}\z/D', $revision)) {
    fwrite(STDERR, "Invalid source revision.\n");
    exit(64);
}

try {
    $root = realpath($rootArg);
    if ($root === false || $root !== '/home/zomorod2/.private/zomorod-business' || is_link($rootArg)) {
        throw new RuntimeException('unexpected-private-root');
    }
    $dbPath = $root . '/management.sqlite3';
    if (!is_file($dbPath) || is_link($dbPath) || !is_readable($dbPath)
        || (fileperms($dbPath) & 0777) !== 0600 || filesize($dbPath) < 4096) {
        throw new RuntimeException('private-ledger-file-unsafe');
    }
    if (!extension_loaded('pdo_sqlite') || !extension_loaded('sqlite3')) {
        throw new RuntimeException('sqlite-extensions-required');
    }
    $db = new PDO('sqlite:file:' . $dbPath . '?mode=rw', null, null, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_TIMEOUT => 12,
    ]);
    $db->exec('PRAGMA foreign_keys=ON; PRAGMA busy_timeout=12000;');
    foreach (['users', 'ledger_accounts', 'journal_entries', 'journal_lines',
        'invoice_payments', 'audit_events'] as $table) {
        $s = $db->prepare("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?");
        $s->execute([$table]);
        if ((int) $s->fetchColumn() !== 1) {
            throw new RuntimeException('required-ledger-schema-missing');
        }
    }
    $admins = (int) $db->query("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1")->fetchColumn();
    if ($admins < 1) {
        throw new RuntimeException('no-active-owner-admin');
    }
    $bankLabels = [
        '1011' => 'بانک ملت - حساب جاری و دسته‌چک',
        '1012' => 'بانک شهر - حساب پس‌انداز و کارت',
    ];
    $inspect = static function (PDO $connection) use ($bankLabels): string {
        $rows = $connection->query("SELECT code,name,type,active FROM ledger_accounts
            WHERE code IN ('1011','1012') ORDER BY code")->fetchAll();
        $hasRegistry = (int) $connection->query("SELECT COUNT(*) FROM sqlite_master
            WHERE type='table' AND name='bank_payment_evidence'")->fetchColumn() === 1;
        if ($rows === [] && !$hasRegistry) {
            return 'missing';
        }
        if (count($rows) !== 2 || !$hasRegistry) {
            throw new RuntimeException('partial-bank-setup-refuses-to-change');
        }
        foreach ($rows as $row) {
            if (($bankLabels[$row['code']] ?? null) !== $row['name']
                || $row['type'] !== 'asset' || (int) $row['active'] !== 1) {
                throw new RuntimeException('bank-chart-conflict');
            }
        }
        $columns = array_column($connection->query('PRAGMA table_info(bank_payment_evidence)')->fetchAll(), 'name');
        if ($columns !== ['id', 'payment_id', 'bank_account_id', 'evidence', 'created_by', 'created_at']) {
            throw new RuntimeException('bank-evidence-schema-conflict');
        }
        return 'configured';
    };
    if ($inspect($db) === 'configured') {
        fwrite(STDOUT, "BANK_CHART=already_configured\nFINANCIAL_TRANSACTIONS_CREATED=0\n");
        exit(0);
    }

    // SQLite's online backup API takes a consistent snapshot even if WAL is enabled.
    $home = dirname(dirname($root));
    umask(0077);
    $backupDir = $home . '/.backups/zm-bank-ledger-setup/' . $revision;
    if (is_link($home . '/.backups') || is_link(dirname($backupDir))) {
        throw new RuntimeException('backup-parent-symlink');
    }
    if (file_exists($backupDir) || is_link($backupDir)) {
        throw new RuntimeException('backup-path-already-exists');
    }
    if (!is_dir(dirname($backupDir)) && !mkdir(dirname($backupDir), 0700, true)) {
        throw new RuntimeException('backup-parent-unavailable');
    }
    if (!mkdir($backupDir, 0700)) {
        throw new RuntimeException('backup-directory-unavailable');
    }
    $backupFile = $backupDir . '/management.before.sqlite3';
    $source = new SQLite3($dbPath, SQLITE3_OPEN_READONLY);
    $backup = new SQLite3($backupFile, SQLITE3_OPEN_READWRITE | SQLITE3_OPEN_CREATE);
    if (!$source->backup($backup)) {
        throw new RuntimeException('consistent-backup-failed');
    }
    $backup->close();
    $source->close();
    chmod($backupFile, 0600);
    clearstatcache(true, $backupFile);
    if ((fileperms($backupFile) & 0777) !== 0600 || filesize($backupFile) < 4096) {
        throw new RuntimeException('backup-verification-failed');
    }

    $db->exec('BEGIN IMMEDIATE');
    try {
        if ($inspect($db) !== 'missing') {
            throw new RuntimeException('concurrent-bank-configuration');
        }
        $s = $db->prepare('INSERT INTO ledger_accounts(code,name,type,active) VALUES(?,?,?,1)');
        foreach ($bankLabels as $code => $label) {
            $s->execute([(string) $code, $label, 'asset']);
        }
        $db->exec('CREATE TABLE bank_payment_evidence (
            id INTEGER PRIMARY KEY,
            payment_id INTEGER NOT NULL UNIQUE REFERENCES invoice_payments(id),
            bank_account_id INTEGER NOT NULL REFERENCES ledger_accounts(id),
            evidence TEXT NOT NULL,
            created_by INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(bank_account_id,evidence))');
        $s = $db->prepare('INSERT INTO audit_events(user_id,verb,subject,entity_id)
            VALUES(NULL,?,?,NULL)');
        $s->execute(['system-configure', 'bank-subledgers']);
        if ($inspect($db) !== 'configured') {
            throw new RuntimeException('bank-chart-postcondition-failed');
        }
        $db->exec('COMMIT');
    } catch (Throwable $e) {
        try { $db->exec('ROLLBACK'); } catch (Throwable $ignored) {}
        throw $e;
    }
    fwrite(STDOUT, "BANK_CHART=configured\nBANK_ACCOUNTS_CREATED=2\nEVIDENCE_REGISTRY=ready\n");
    fwrite(STDOUT, "FINANCIAL_TRANSACTIONS_CREATED=0\nBACKUP=owner_private\n");
    exit(0);
} catch (Throwable $e) {
    error_log('bank_chart_setup_refused: ' . $e->getMessage());
    fwrite(STDERR, "BANK_CHART=not_changed_or_refused\n");
    exit(1);
}
