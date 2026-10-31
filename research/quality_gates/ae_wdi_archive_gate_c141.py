#!/usr/bin/env python3
"""Offline, fail-closed World Bank Indicators API response archivist.

Usage: python ae_wdi_archive_gate_c141.py official.json output/ --country IND --indicator SL.AGR.EMPL.ZS
Supply exact response bytes downloaded independently from api.worldbank.org/v2.
No HTTP fetch, no fabricated observations, no mutation of the input file.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def archive(raw: bytes, country: str, indicator: str):
    digest = hashlib.sha256(raw).hexdigest()
    payload = json.loads(raw.decode('utf-8-sig'))
    if not (isinstance(payload, list) and len(payload) == 2):
        raise ValueError('Expected World Bank v2 [metadata, observations] JSON')
    meta, records = payload
    if not isinstance(meta, dict) or not isinstance(records, list):
        raise ValueError('Invalid metadata or records')
    if meta.get('page') != 1 or int(meta.get('pages', 0)) != 1:
        raise ValueError('Pagination incomplete: fetch all pages before archiving')
    if int(meta.get('total', -1)) != len(records):
        raise ValueError('Metadata total differs from observation count')
    if not records:
        raise ValueError('No observations')
    seen = set()
    out = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError('Malformed observation')
        country_obj = record.get('country') or {}
        indicator_obj = record.get('indicator') or {}
        if record.get('countryiso3code') != country or indicator_obj.get('id') != indicator:
            raise ValueError('Country or indicator mismatch')
        date = str(record.get('date', ''))
        if not (len(date) == 4 and date.isdigit()):
            raise ValueError('Expected annual observation')
        if date in seen:
            raise ValueError('Duplicate year')
        seen.add(date)
        value = record.get('value')
        if value is not None and (isinstance(value, bool) or not isinstance(value, (float, int))):
            raise ValueError('Invalid numeric value')
        if value is not None and not math.isfinite(value):
            raise ValueError('Non-finite numeric value forbidden')
        if value is not None and indicator == 'SL.AGR.EMPL.ZS' and not (0 <= value <= 100):
            raise ValueError('Agricultural employment share outside 0–100 percent')
        out.append({'country_iso3': country, 'indicator': indicator, 'year': date,
                    'value': '' if value is None else repr(value),
                    'country_label': country_obj.get('value', '')})
    out.sort(key=lambda x: x['year'])
    manifest = {'sha256_original_response': digest, 'byte_count': len(raw),
                'country_iso3': country, 'indicator': indicator,
                'records': len(out), 'years': [r['year'] for r in out],
                'source_claim': 'Caller-supplied World Bank v2 JSON; origin must be independently authenticated',
                'origin_verified_by_this_tool': False,
                'vintage_verified_by_this_tool': False,
                'raw_data_retained': True}
    return out, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('response_json', type=Path)
    parser.add_argument('output_directory', type=Path)
    parser.add_argument('--country', default='IND')
    parser.add_argument('--indicator', required=True)
    args = parser.parse_args()
    raw = args.response_json.read_bytes()
    rows, manifest = archive(raw, args.country, args.indicator)
    outdir = args.output_directory
    outdir.mkdir(parents=True, exist_ok=True)
    original = outdir / (args.indicator + '_response.json')
    if original.exists():
        raise FileExistsError('Refusing to overwrite an archived raw response')
    original.write_bytes(raw)
    with (outdir / (args.indicator + '_normalized.csv')).open('x', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (outdir / (args.indicator + '_provenance.json')).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
