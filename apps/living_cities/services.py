"""Authoritative transactional gameplay and physical-code claims for Living Cities.

No blockchain transfers or private keys live in this module.
"""
import base64
import hashlib
import hmac
import re
import secrets

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import AdultEligibility, City, ManufactureOrder, MigrationReceipt, PhysicalCodeClaim, PhysicalUnit, Realm, Stock


RESOURCE_INITIAL = {"WOOD": 70, "FOOD": 80, "STONE": 60, "CRYSTAL": 15}
EXPEDITION_COST = {"WOOD": 30, "FOOD": 20, "CRYSTAL": 5}
BIOMES = ["MEADOW", "COAST", "DESERT", "TUNDRA", "FOREST", "HIGHLAND"]


def _city_payload(city):
    return {
        "id": city.id, "code": city.code, "name": city.name,
        "biome": city.biome, "level": city.level, "population": city.population,
        "resources": {r.kind: r.amount for r in Stock.objects.filter(city=city).order_by("kind")},
    }


def _realm_locked(user):
    realm, _ = Realm.objects.get_or_create(owner=user)
    return Realm.objects.select_for_update().get(pk=realm.pk)


@transaction.atomic
def ensure_home(user):
    realm = _realm_locked(user)
    if realm.active_city_id:
        return realm
    city, created = City.objects.get_or_create(
        owner=user, code="HOME", defaults={"name": "Origin", "biome": "MEADOW"}
    )
    if created:
        for kind, amount in RESOURCE_INITIAL.items():
            Stock.objects.create(city=city, kind=kind, amount=amount)
    realm.active_city = city
    realm.version += 1
    realm.save(update_fields=["active_city", "version", "updated_at"])
    return realm


@transaction.atomic
def explore_city(user, name):
    name = str(name).strip()
    if not 2 <= len(name) <= 64:
        raise ValidationError("invalid_city_name")
    realm = ensure_home(user)
    realm = Realm.objects.select_for_update().get(pk=realm.pk)
    home = City.objects.select_for_update().get(pk=realm.active_city_id)
    costs = list(Stock.objects.select_for_update().filter(city=home, kind__in=EXPEDITION_COST))
    by_kind = {stock.kind: stock for stock in costs}
    if len(costs) != len(EXPEDITION_COST) or any(by_kind[kind].amount < amount for kind, amount in EXPEDITION_COST.items()):
        raise ValidationError("insufficient_expedition_resources")
    for kind, amount in EXPEDITION_COST.items():
        stock = by_kind[kind]
        stock.amount -= amount
        stock.save(update_fields=["amount"])
    count = City.objects.filter(owner=user).count()
    city = City.objects.create(owner=user, code=f"C{count + 1:05d}", name=name, biome=BIOMES[count % len(BIOMES)])
    for kind in RESOURCE_INITIAL:
        Stock.objects.create(city=city, kind=kind, amount=0)
    realm.version += 1
    realm.save(update_fields=["version", "updated_at"])
    return city


@transaction.atomic
def migrate_city(user, destination_id, idempotency_key):
    key = str(idempotency_key).strip()
    if not 8 <= len(key) <= 96:
        raise ValidationError("invalid_idempotency_key")
    realm = ensure_home(user)
    realm = Realm.objects.select_for_update().get(pk=realm.pk)
    existing = MigrationReceipt.objects.filter(owner=user, idempotency_key=key).first()
    if existing:
        if existing.to_city_id != destination_id:
            raise ValidationError("idempotency_conflict")
        return existing, True
    destination = City.objects.filter(pk=destination_id, owner=user).first()
    if not destination:
        raise PermissionDenied("city_not_owned")
    if realm.active_city_id == destination.id:
        raise ValidationError("already_in_city")
    receipt = MigrationReceipt.objects.create(
        owner=user, idempotency_key=key, from_city_id=realm.active_city_id, to_city=destination
    )
    realm.active_city = destination
    realm.version += 1
    realm.save(update_fields=["active_city", "version", "updated_at"])
    return receipt, False


def city_snapshot(user):
    realm = ensure_home(user)
    return {
        "version": realm.version,
        "active_city_id": realm.active_city_id,
        "cities": [_city_payload(c) for c in City.objects.filter(owner=user).order_by("id")],
    }


@transaction.atomic
def harvest_resources(user, city_id):
    city = City.objects.select_for_update().filter(owner=user, pk=city_id).first()
    if not city:
        raise PermissionDenied("city_not_owned")
    now = timezone.now()
    minutes = min(1440, max(0, int((now - city.last_harvest_at).total_seconds() // 60)))
    yields = {"WOOD": 2, "FOOD": 3, "STONE": 1, "CRYSTAL": 1}
    harvested = {}
    if minutes:
        for stock in Stock.objects.select_for_update().filter(city=city):
            possible = min(stock.capacity - stock.amount, max(0, minutes * yields[stock.kind] * city.level))
            if possible:
                stock.amount += possible
                stock.save(update_fields=["amount"])
            harvested[stock.kind] = possible
        city.last_harvest_at = now
        city.save(update_fields=["last_harvest_at"])
    return {"city_id": city.id, "minutes": minutes, "earned": harvested, "city": _city_payload(city)}


def _digest(code):
    canonical = re.sub(r"[\s-]", "", str(code)).upper()
    if not re.fullmatch(r"[A-Z2-7]{32}", canonical):
        raise ValidationError("invalid_code")
    pepper = getattr(settings, "LIVING_CITIES_CODE_PEPPER", "")
    if not pepper:
        raise ValidationError("code_security_key_unconfigured")
    return hmac.new(
        pepper.encode("utf-8"),
        b"living-cities-code-v1:" + canonical.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()


def _format_code(code):
    return "-".join(code[i:i+4] for i in range(0, len(code), 4))


@transaction.atomic
def manufacture_units(operator, *, order_ref, order_evidence, sku, quantity):
    if not operator.is_authenticated or not operator.is_staff:
        raise PermissionDenied("staff_required")
    order_ref, order_evidence, sku = [str(s).strip() for s in (order_ref, order_evidence, sku)]
    if not order_ref or not order_evidence or not sku or len(order_ref) > 160 or len(order_evidence) > 240 or len(sku) > 96:
        raise ValidationError("verified_order_evidence_required")
    if type(quantity) is not int or not 1 <= quantity <= 500:
        raise ValidationError("invalid_quantity")
    # A repeated manufacturing request must never reissue secret labels.
    # The unique order reservation is a transactional, database-enforced mutex.
    try:
        with transaction.atomic():
            ManufactureOrder.objects.create(
                order_ref=order_ref, order_evidence=order_evidence,
                sku=sku, quantity=quantity, issued_by=operator,
            )
    except IntegrityError as exc:
        raise ValidationError("order_already_has_labels") from exc
    labels = []
    for _ in range(quantity):
        code = base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")
        serial = "LC-" + secrets.token_hex(12).upper()
        PhysicalUnit.objects.create(
            order_ref=order_ref, order_evidence=order_evidence,
            sku=sku, serial=serial, secret_digest=_digest(code)
        )
        labels.append({"serial": serial, "sku": sku, "secret_once": _format_code(code)})
    return labels


@transaction.atomic
def record_delivery(operator, serial, evidence):
    if not operator.is_authenticated or not operator.is_staff:
        raise PermissionDenied("staff_required")
    evidence = str(evidence).strip()
    if not evidence or len(evidence) > 240:
        raise ValidationError("proof_of_delivery_required")
    unit = PhysicalUnit.objects.select_for_update().filter(serial=serial).first()
    if not unit:
        raise ValidationError("unknown_serial")
    if unit.status == "DELIVERED" and unit.delivery_evidence == evidence:
        return unit
    if unit.status != "PRINTED":
        raise ValidationError("invalid_product_state")
    unit.status = "DELIVERED"
    unit.delivered_at = timezone.now()
    unit.delivery_evidence = evidence
    unit.save(update_fields=["status", "delivered_at", "delivery_evidence"])
    return unit


@transaction.atomic
def submit_physical_code(user, code):
    if not user.is_authenticated:
        raise PermissionDenied("login_required")
    eligibility = AdultEligibility.objects.filter(
        owner=user, adult_verified=True, jurisdiction_allowed=True
    ).first()
    if eligibility is None:
        raise PermissionDenied("crypto_age_or_region_restriction")
    digest = _digest(code)
    unit = PhysicalUnit.objects.select_for_update().filter(secret_digest=digest).first()
    if unit is None:
        raise ValidationError("invalid_or_unavailable_code")
    if unit.status == "CLAIMED":
        prior = PhysicalCodeClaim.objects.filter(unit=unit, claimant=user).first()
        if prior:
            return prior, True
        raise ValidationError("code_already_claimed")
    if unit.status != "DELIVERED":
        raise ValidationError("code_not_claimable")
    unit.status = "CLAIMED"
    unit.save(update_fields=["status"])
    claim = PhysicalCodeClaim.objects.create(unit=unit, claimant=user)
    return claim, False
