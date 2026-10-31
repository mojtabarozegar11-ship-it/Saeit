<?php
/** PHP issuer for the isolated Zomorod unified-login ticket contract.
 *
 * Not routed or activated by this file. Production caller MUST check an active
 * authenticated PHP session, fresh DB role and CSRF, then emit a same-origin
 * HTTPS POST directly to the designated Django consumer. Never log tokens.
 * The shared key MUST come from a server-private 0600 file, not from source.
 */
declare(strict_types=1);

function zmOfficeSsoB64(string $data): string {
    return rtrim(strtr(base64_encode($data), '+/', '-_'), '=');
}

function zmOfficeSsoIssue(int $userId, string $role, string $secret, ?int $issuedAt = null): string {
    if ($userId < 1 || !in_array($role, ['admin', 'accountant', 'manager'], true)) {
        throw new InvalidArgumentException('SSO identity is not authorized');
    }
    if (strlen($secret) < 32) {
        throw new InvalidArgumentException('SSO server key unavailable');
    }
    $issuedAt = $issuedAt ?? time();
    if ($issuedAt < 1 || $issuedAt > 4102444800) {
        throw new InvalidArgumentException('SSO issue time invalid');
    }
    $claims = [
        'iss' => 'zomorod-business-php',
        'aud' => 'zomorod-company-office',
        'iat' => $issuedAt,
        'exp' => $issuedAt + 30,
        'nonce' => zmOfficeSsoB64(random_bytes(16)),
        'uid' => $userId,
        'role' => $role,
    ];
    $encoded = zmOfficeSsoB64(json_encode($claims, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES));
    $message = 'v1.'.$encoded;
    return $message.'.'.zmOfficeSsoB64(hash_hmac('sha256', $message, $secret, true));
}
