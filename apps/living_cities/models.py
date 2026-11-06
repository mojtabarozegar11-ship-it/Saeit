from django.conf import settings
from django.db import models


class City(models.Model):
    BIOMES = [
        ("MEADOW", "Meadow"), ("COAST", "Coast"), ("DESERT", "Desert"),
        ("TUNDRA", "Tundra"), ("FOREST", "Forest"), ("HIGHLAND", "Highland"),
    ]
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="living_cities")
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=96)
    biome = models.CharField(max_length=16, choices=BIOMES, default="MEADOW")
    level = models.PositiveIntegerField(default=1)
    population = models.PositiveIntegerField(default=100)
    last_harvest_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["owner", "code"], name="lc_city_owner_code")]


class Realm(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="living_realm")
    active_city = models.ForeignKey(City, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    version = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


class Stock(models.Model):
    KINDS = [("WOOD", "Wood"), ("FOOD", "Food"), ("STONE", "Stone"), ("CRYSTAL", "Crystal")]
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="stocks")
    kind = models.CharField(max_length=12, choices=KINDS)
    amount = models.PositiveBigIntegerField(default=0)
    capacity = models.PositiveBigIntegerField(default=10000)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["city", "kind"], name="lc_stock_city_kind")]


class MigrationReceipt(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    idempotency_key = models.CharField(max_length=96)
    from_city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="+")
    to_city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["owner", "idempotency_key"], name="lc_migration_once")]


class ManufactureOrder(models.Model):
    order_ref = models.CharField(max_length=160, unique=True)
    order_evidence = models.CharField(max_length=240)
    sku = models.CharField(max_length=96)
    quantity = models.PositiveIntegerField()
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    issued_at = models.DateTimeField(auto_now_add=True)


class PhysicalUnit(models.Model):
    STATES = [
        ("PRINTED", "Printed"), ("DELIVERED", "Delivered"),
        ("CLAIMED", "Claimed"), ("VOIDED", "Voided"), ("QUARANTINED", "Quarantined"),
    ]
    order_ref = models.CharField(max_length=160)
    order_evidence = models.CharField(max_length=240)
    sku = models.CharField(max_length=96)
    serial = models.CharField(max_length=64, unique=True)
    secret_digest = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=16, choices=STATES, default="PRINTED")
    delivery_evidence = models.CharField(max_length=240, blank=True)
    printed_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["order_ref", "serial"], name="lc_order_unit_unique")]


class AdultEligibility(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lc_crypto_eligibility")
    adult_verified = models.BooleanField(default=False)
    jurisdiction_allowed = models.BooleanField(default=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)


class PhysicalCodeClaim(models.Model):
    STATES = [("PENDING_POLICY", "Pending policy"), ("FROZEN", "Frozen"), ("REJECTED", "Rejected")]
    unit = models.OneToOneField(PhysicalUnit, on_delete=models.PROTECT, related_name="claim")
    claimant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATES, default="PENDING_POLICY")
    submitted_at = models.DateTimeField(auto_now_add=True)
    # This is an entitlement claim, NOT a token balance or a chain transfer.
    # Owner confirmed MOJ1 on TRON; no monetary amount or transfer is promised.
    reward_symbol = models.CharField(max_length=16, default="MOJ1", editable=False)
    reward_network = models.CharField(max_length=24, default="TRON", editable=False)
    # Contract identity, decimals, claim amount and transfer remain unverified.


import django.utils.timezone


class PlayerWorld(models.Model):
    """Server-authoritative browser game state; local client saves grant no entitlements."""
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="living_world"
    )
    payload = models.JSONField(default=dict)
    revision = models.PositiveBigIntegerField(default=0)
    last_simulated_at = models.DateTimeField(default=django.utils.timezone.now)


class WorldActionReceipt(models.Model):
    """Immutable replay protection for every state-changing action."""
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    action_key = models.CharField(max_length=96)
    action_digest = models.CharField(max_length=64)
    revision = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "action_key"], name="lc_world_action_owner_key"
            ),
        ]


class PlayerTycoon(models.Model):
    """Authoritative endless-business state; browser saves are offline-only."""
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="living_tycoon"
    )
    payload = models.JSONField(default=dict)
    revision = models.PositiveBigIntegerField(default=0)
    last_simulated_at = models.DateTimeField(default=django.utils.timezone.now)


class TycoonActionReceipt(models.Model):
    """Small immutable receipt preventing duplicate business actions."""
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    action_key = models.CharField(max_length=96)
    action_digest = models.CharField(max_length=64)
    revision = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "action_key"], name="lc_tycoon_action_owner_key"
            ),
        ]


class TycoonMarketingReceipt(models.Model):
    """Permanent one-claim/one-boost record independent of bounded JSON history."""
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    claim = models.OneToOneField(
        PhysicalCodeClaim, on_delete=models.PROTECT, related_name="marketing_receipt"
    )
    duration_seconds = models.PositiveIntegerField(default=3600)
    revision = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)



class LoginAttemptBucket(models.Model):
    """Shared-database password-guessing limit; never store IPs or usernames."""

    key_digest = models.CharField(max_length=64, unique=True, editable=False)
    failures = models.PositiveSmallIntegerField(default=0)
    first_failure_at = models.DateTimeField(default=django.utils.timezone.now)
    blocked_until = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return "Living Cities login protection"
