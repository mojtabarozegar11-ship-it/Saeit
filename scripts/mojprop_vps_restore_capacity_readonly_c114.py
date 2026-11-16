#!/usr/bin/env python3
"""C114: independent VPS storage screening for Moj Prop DB restoration.

Read-only metadata on the established owner factory-vps runner. The cPanel
connected database is already measured as >8 GiB (C113). This script checks
only whether the existing separate VPS has even the MINIMUM plausible space
for a double-DB restore, and whether its known non-root local mounts include
a separate >=40 GiB candidate. It never transfers DB bytes or authorizes a
restore, service startup, deletion, customer payment, or deployment.
"""
import json
import os
import pwd
import stat
from pathlib import Path

from scripts.mpw_vps_mount_capacity_readonly_20261105 import inspect

GIB = 1024 ** 3
MIB = 1024 ** 2
MIN_KNOWN_DB_LOWER_BOUND = 8 * GIB
MIN_RESTORE_LOWER_BOUND = 2 * MIN_KNOWN_DB_LOWER_BOUND + 256 * MIB
EXPECTED_OWNER = "githubops"
FACTORY_ROOT = Path("/home/githubops/factory-runtime")
HOME = Path("/home/githubops")


def safe_owned_root(path):
    try:
        info = path.lstat()
        return (stat.S_ISDIR(info.st_mode)
                and not stat.S_ISLNK(info.st_mode)
                and info.st_uid == os.geteuid())
    except OSError:
        return False


def bounded_gib(value):
    if type(value) is not int or value < 0:
        return "unknown"
    gib = value // GIB
    if gib < 2:
        return "0-2"
    if gib < 4:
        return "2-4"
    if gib < 8:
        return "4-8"
    if gib < 16:
        return "8-16"
    if gib < 24:
        return "16-24"
    if gib < 40:
        return "24-40"
    return ">=40"


def classify_mounts(mounts, owner_verified, factory_root_verified):
    """No guesses: the source DB's exact size and actual usable VPS quota
    are NOT known here. Passing a lower bound is never restoration proof.
    """
    report = {
        "schema": "mojprop.vps.restore_screen.readonly.v1",
        "read_only": True,
        "owner_verified": bool(owner_verified),
        "factory_root_verified": bool(factory_root_verified),
        "minimum_two_db_plus_headroom_mib": MIN_RESTORE_LOWER_BOUND // MIB,
        "exact_connected_db_size_available_here": False,
        "vps_home_free_gib_bucket": "unknown",
        "largest_independent_local_free_gib_bucket": "unknown",
        "mount_inventory_complete": False,
        "home_above_minimum_screen": False,
        "independent_local_above_minimum_screen": False,
        "independent_40gib_candidate_with_write_hint": False,
        "restore_destination_verified": False,
        "restoration_test_performed": False,
        "encryption_and_key_recovery_verified": False,
        "tenant_or_process_isolation_verified": False,
        "live_services_modified": False,
        "database_or_customer_bytes_read": False,
        "files_created_or_deleted": False,
        "production_release_authorized": False,
        "customer_payment_collected": False,
    }
    if not (owner_verified and factory_root_verified
            and type(mounts) is dict
            and mounts.get("classification") == "READ_ONLY_MPW_VPS_DISTINCT_LOCAL_MOUNTS"):
        report["screen_result"] = "unverified_context"
        return report
    home = mounts.get("home_free_bytes")
    independent = mounts.get("largest_independent_free_bytes")
    candidates = mounts.get("independent_devices_with_write_hint_and_size_floor")
    count = mounts.get("independent_local_device_count")
    inventory = mounts.get("inventory_complete")
    if not (type(home) is int and home >= 0
            and type(independent) is int and independent >= 0
            and type(candidates) is int and candidates >= 0
            and type(count) is int and count >= 0
            and type(inventory) is bool
            and count >= candidates):
        report["screen_result"] = "unverified_mount_metadata"
        return report
    report["vps_home_free_gib_bucket"] = bounded_gib(home)
    report["largest_independent_local_free_gib_bucket"] = bounded_gib(independent)
    report["mount_inventory_complete"] = inventory
    if not inventory:
        report["screen_result"] = "incomplete_mount_inventory"
        return report
    report["home_above_minimum_screen"] = home > MIN_RESTORE_LOWER_BOUND
    report["independent_local_above_minimum_screen"] = (
        independent > MIN_RESTORE_LOWER_BOUND)
    report["independent_40gib_candidate_with_write_hint"] = candidates > 0
    report["screen_result"] = (
        "at_least_one_size_candidate_unproven"
        if report["home_above_minimum_screen"] or
           report["independent_local_above_minimum_screen"]
        else "no_known_location_meets_minimum")
    return report


def run():
    try:
        owner_ok = pwd.getpwuid(os.geteuid()).pw_name == EXPECTED_OWNER
    except (KeyError, OSError):
        owner_ok = False
    root_ok = owner_ok and safe_owned_root(HOME) and safe_owned_root(FACTORY_ROOT)
    raw = None
    if root_ok:
        try:
            raw = inspect(home=HOME)
        except (OSError, ValueError, KeyError, TypeError):
            raw = None
    return classify_mounts(raw, owner_ok, root_ok)


if __name__ == "__main__":
    print("MOJPROP_C114_VPS_RESTORE_SCREEN=" + json.dumps(run(), sort_keys=True))
