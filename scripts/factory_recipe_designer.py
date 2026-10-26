#!/usr/bin/env python3
"""Offline arithmetic program synthesis, not a general-purpose AI inventor.

Searches bounded expression trees against training examples, then checks unseen
acceptance examples. Emits actual Python, tests, documentation and provenance.
No fixed catalog size; unsupported families stay explicitly blocked. Does not
certify scientific, market or commercial quality. Python 3.8+, stdlib only.
"""
import ast
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time

SCHEMA = 'saeit.factory.design-request.v1'
IDENT = re.compile(r'^[a-z][a-z0-9_]{1,47}$')
ORIGINS = {'site_need', 'customer_request', 'market_demand', 'factory_invention'}
MAX_BYTES = 200000
MAX_STATES = 12000
MAX_NODES = 7


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def private(path):
    if path.is_symlink():
        raise ValueError('DESIGN_SYMLINK_DIRECTORY')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(str(path), 0o700)


def save(path, value):
    private(path.parent)
    if path.is_symlink():
        raise ValueError('DESIGN_SYMLINK_FILE')
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + '\n'
    fd, stage = tempfile.mkstemp(dir=str(path.parent), prefix='.design-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text); stream.flush(); os.fsync(stream.fileno())
        os.chmod(stage, 0o600)
        os.replace(stage, str(path))
    finally:
        if os.path.exists(stage): os.unlink(stage)


def read(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError('DESIGN_UNSAFE_INPUT')
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict): raise ValueError('DESIGN_OBJECT_REQUIRED')
    return value


def number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError('FINITE_NUMBER_REQUIRED')
    if len(str(value)) > 80: raise ValueError('NUMBER_TOO_LONG')
    try: result = Decimal(str(value))
    except InvalidOperation: raise ValueError('FINITE_NUMBER_REQUIRED')
    if not result.is_finite() or abs(result) > Decimal('1e12'):
        raise ValueError('NUMBER_OUT_OF_RANGE')
    return result


def validate(spec):
    if spec.get('schema') != SCHEMA or spec.get('origin') not in ORIGINS:
        raise ValueError('DESIGN_SCHEMA_OR_ORIGIN_INVALID')
    if spec.get('family_id') not in ('F27','F28'): raise ValueError('DESIGN_FAMILY_ADAPTER_NOT_IMPLEMENTED')
    if spec.get('family_id')=='F27' and importlib.util.find_spec('openpyxl') is None:
        raise ValueError('DESIGN_FAMILY_TOOL_UNAVAILABLE:openpyxl')
    if spec.get('kind') != 'arithmetic_program': raise ValueError('DESIGN_KIND_NOT_IMPLEMENTED')
    for key in ('title', 'problem', 'output_unit', 'limitations'):
        if not isinstance(spec.get(key), str) or not (1 if key=='output_unit' else 3) <= len(spec[key]) <= 2000:
            raise ValueError('DESIGN_MISSING_FIELD:' + key)
    fields = spec.get('inputs')
    if not isinstance(fields, list) or not 1 <= len(fields) <= 4:
        raise ValueError('DESIGN_INPUT_FIELDS_REQUIRED')
    names = []
    for item in fields:
        if (not isinstance(item, dict) or not IDENT.fullmatch(str(item.get('name','')))
                or not isinstance(item.get('unit'), str) or not item['unit']):
            raise ValueError('DESIGN_INVALID_INPUT_FIELD')
        for bound in ('minimum','maximum'):
            if bound in item: number(item[bound])
        if 'minimum' in item and 'maximum' in item and number(item['minimum'])>number(item['maximum']):
            raise ValueError('DESIGN_INPUT_RANGE_INVALID')
        if 'integral' in item and not isinstance(item['integral'],bool):
            raise ValueError('DESIGN_INTEGRAL_FLAG_INVALID')
        names.append(item['name'])
    if len(set(names)) != len(names): raise ValueError('DESIGN_DUPLICATE_INPUT')
    groups = []
    for key, minimum in (('training_examples', 5), ('acceptance_examples', 3)):
        rows = spec.get(key)
        if not isinstance(rows, list) or not minimum <= len(rows) <= 25:
            raise ValueError('DESIGN_EXAMPLES_REQUIRED:' + key)
        normalized = []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('inputs'), dict) or set(row['inputs']) != set(names):
                raise ValueError('DESIGN_EXAMPLE_SCHEMA')
            values=tuple(number(row['inputs'][n]) for n in names)
            for value,field in zip(values,fields):
                if ('minimum' in field and value<number(field['minimum']) or
                        'maximum' in field and value>number(field['maximum']) or
                        field.get('integral') and value!=value.to_integral_value()):
                    raise ValueError('DESIGN_EXAMPLE_OUTSIDE_DOMAIN')
            normalized.append((values, number(row.get('output'))))
        if len(set(x[0] for x in normalized)) != len(normalized):
            raise ValueError('DESIGN_DUPLICATE_EXAMPLE')
        groups.append(normalized)
    if set(x[0] for x in groups[0]) & set(x[0] for x in groups[1]):
        raise ValueError('DESIGN_HOLDOUT_LEAKAGE')
    return names, groups[0], groups[1]


def operation(op, a, b):
    with localcontext() as context:
        context.prec = 40
        if op == '+': value = a + b
        elif op == '-': value = a - b
        elif op == '*': value = a * b
        elif op == '/' and b != 0: value = a / b
        else: raise ValueError('ZERO_DIVISION')
    if not value.is_finite() or abs(value) > Decimal('1e24'):
        raise ValueError('EXPRESSION_OUT_OF_RANGE')
    return value


def evaluate(tree, values):
    if isinstance(tree, int): return values[tree]
    op, a, b = tree
    return operation(op, evaluate(a, values), evaluate(b, values))


def close(a, b):
    return abs(a-b) <= Decimal('1e-12') * max(Decimal(1), abs(b))


def synthesize(names, training):
    """Semantic enumeration uses ONLY training inputs/targets, never holdout."""
    target = tuple(row[1] for row in training)
    by_size = {1: []}
    seen = set()
    searched = 0
    for i in range(len(names)):
        values = tuple(row[0][i] for row in training)
        if values in seen: continue
        seen.add(values); by_size[1].append((i, values))
        if all(close(a,b) for a,b in zip(values,target)): return i, len(seen)
    for size in range(3, MAX_NODES + 1, 2):
        by_size[size] = []
        for left_size in range(1,size-1,2):
            right_size = size-1-left_size
            for a, av in by_size.get(left_size, []):
                for b, bv in by_size.get(right_size, []):
                    for op in ('+', '-', '*', '/'):
                        searched += 1
                        if searched > MAX_STATES:
                            raise ValueError('DESIGN_SEARCH_BUDGET_EXHAUSTED')
                        try: values = tuple(operation(op,x,y) for x,y in zip(av,bv))
                        except (ValueError, ArithmeticError): continue
                        if values in seen: continue
                        seen.add(values)
                        tree = (op,a,b)
                        if all(close(x,y) for x,y in zip(values,target)):
                            return tree, searched
                        by_size[size].append((tree, values))
    raise ValueError('DESIGN_NO_PROGRAM_FOUND')


def expression(tree):
    if isinstance(tree,int): return 'v[' + str(tree) + ']'
    return '('+expression(tree[1])+' '+tree[0]+' '+expression(tree[2])+')'


def compile_recipe(spec, recipes):
    names, train, holdout = validate(spec)
    tree, searched = synthesize(names, train)
    for inputs, expected in holdout:
        try: matched = close(evaluate(tree,inputs),expected)
        except (ValueError,ArithmeticError): matched=False
        if not matched: raise ValueError('DESIGN_INDEPENDENT_ACCEPTANCE_FAILED')
    # Names/titles/example changes alone are not a new functional product.
    functional_hash = digest({'tree':tree,'input_units':[x['unit'] for x in spec['inputs']],
                              'output_unit':spec['output_unit'],
                              'input_domains':[{k:f[k] for k in ('minimum','maximum','integral') if k in f}
                                               for f in spec['inputs']]})
    family=spec['family_id']
    recipe = ('synth_' if family=='F28' else 'sheet_') + functional_hash[:24]
    private(recipes)
    destination = recipes / recipe
    provenance = {'schema':'saeit.factory.synthesis-receipt.v1',
                  'request_sha256':digest(spec),'functional_sha256':functional_hash,
                  'family_id':family,'recipe':recipe,'expression_tree':tree,
                  'design_method':'bounded_arithmetic_program_synthesis',
                  'search_states_evaluated':searched,'training_examples':len(train),
                  'heldout_examples_passed':len(holdout),'general_ai_invention':False,
                  'scientific_review_completed':False,'commercial_release':False,
                   'generator_capability_revision':'verified-grouped-statistics-v5'}
    if destination.exists():
        saved = read(destination/'design_receipt.json')
        if saved.get('functional_sha256') != functional_hash:
            raise ValueError('DESIGN_RECIPE_ID_COLLISION')
        return dict(provenance, created=False)
    code = '''"""Generated deterministic arithmetic planning tool; read README for limits."""
from decimal import Decimal, InvalidOperation, localcontext
import json
import sys
NAMES = %r
FIELDS = %r

def calculate(data):
    if not isinstance(data, dict) or set(data) != set(NAMES):
        raise ValueError('EXACT_INPUT_FIELDS_REQUIRED')
    v = []
    for name, field in zip(NAMES,FIELDS):
        value = data[name]
        if isinstance(value, bool) or not isinstance(value, (str,int,float)) or len(str(value)) > 80:
            raise ValueError('FINITE_NUMBER_REQUIRED')
        try: number = Decimal(str(value))
        except InvalidOperation: raise ValueError('FINITE_NUMBER_REQUIRED')
        if not number.is_finite() or abs(number) > Decimal('1e12'):
            raise ValueError('NUMBER_OUT_OF_RANGE')
        if ('minimum' in field and number < Decimal(str(field['minimum'])) or
                'maximum' in field and number > Decimal(str(field['maximum'])) or
                field.get('integral') and number != number.to_integral_value()):
            raise ValueError('INPUT_OUTSIDE_DOMAIN')
        v.append(number)
    try:
        with localcontext() as context:
            context.prec = 40
            result = %s
    except ArithmeticError as error:
        raise ValueError('UNDEFINED_RESULT') from error
    if not result.is_finite() or abs(result) > Decimal('1e24'):
        raise ValueError('RESULT_OUT_OF_RANGE')
    return {'result': str(result), 'unit': %r}

# BATCH_API_V2_START
def calculate_batch(records):
    # A bad row aborts the bounded batch without returning a partial result.
    if not isinstance(records,list) or not 1 <= len(records) <= 100:
        raise ValueError('BATCH_INPUT_LIMIT_EXCEEDED')
    return {'count':len(records), 'results':[calculate(row) for row in records]}
# BATCH_API_V2_END

# STATS_API_V3_START
def calculate_statistics(records):
    """Strict, exact-Decimal descriptive summary of a validated customer batch."""
    batch = calculate_batch(records)
    results = [Decimal(item['result']) for item in batch['results']]
    with localcontext() as context:
        context.prec = 40
        total = sum(results, Decimal(0))
        mean = total / Decimal(batch['count'])
    if not total.is_finite() or not mean.is_finite():
        raise ValueError('STATISTICS_OUT_OF_RANGE')
    return {'count':batch['count'], 'unit':batch['results'][0]['unit'],
            'sum':str(total), 'minimum':str(min(results)),
            'maximum':str(max(results)), 'mean':str(mean)}
# STATS_API_V3_END

# DISTRIBUTION_API_V4_START
def calculate_distribution(records):
    """Exact-Decimal empirical dispersion and interpolated quartiles.

    These describe the supplied records only, without invented probabilities
    or claims about future prices, crop yields or market risk.
    """
    batch = calculate_batch(records)
    values = sorted(Decimal(item['result']) for item in batch['results'])
    with localcontext() as context:
        context.prec = 50
        count = Decimal(len(values))
        mean = sum(values, Decimal(0)) / count
        variance = sum(((value - mean) ** 2 for value in values), Decimal(0)) / count
        def percentile(level):
            position = (count - 1) * Decimal(level) / Decimal(100)
            low = int(position)
            part = position - Decimal(low)
            high = min(low + 1, len(values) - 1)
            return values[low] * (Decimal(1) - part) + values[high] * part
        quartiles = {label: str(percentile(level))
                     for label, level in (('p25', 25), ('median', 50), ('p75', 75))}
    return {'count': len(values), 'unit': batch['results'][0]['unit'],
            'minimum': str(values[0]), 'maximum': str(values[-1]),
            'population_variance': str(variance), **quartiles}
# DISTRIBUTION_API_V4_END

# GROUPED_STATISTICS_API_V5_START
def calculate_grouped_statistics(records, group_by):
    """Summarize validated batch results by one declared numeric input field."""
    if not isinstance(group_by, str) or group_by not in NAMES:
        raise ValueError('GROUP_FIELD_REQUIRED')
    batch = calculate_batch(records)
    groups = {}
    for row, result in zip(records, batch['results']):
        key = Decimal(str(row[group_by]))
        groups.setdefault(key, []).append(Decimal(result['result']))
    summaries = []
    with localcontext() as context:
        context.prec = 50
        for key in sorted(groups):
            values = groups[key]
            total = sum(values, Decimal(0))
            summaries.append({'group_value': str(key), 'count': len(values),
                              'sum': str(total), 'minimum': str(min(values)),
                              'maximum': str(max(values)),
                              'mean': str(total / Decimal(len(values)))})
    return {'group_by': group_by, 'unit': batch['results'][0]['unit'],
            'groups': summaries}
# GROUPED_STATISTICS_API_V5_END

if __name__ == '__main__':
    incoming=json.load(sys.stdin)
    print(json.dumps(calculate_batch(incoming) if isinstance(incoming,list)
                     else calculate(incoming), sort_keys=True))
''' % (names,spec['inputs'],expression(tree),spec['output_unit'])
    examples = spec['training_examples']+spec['acceptance_examples']
    tests = '''import unittest
from decimal import Decimal, localcontext
from calculator import calculate
# BATCH_TESTS_V2_START
from calculator import calculate_batch
# BATCH_TESTS_V2_END
# STATS_TESTS_V3_START
from calculator import calculate_statistics
# STATS_TESTS_V3_END
# DISTRIBUTION_TESTS_V4_START
from calculator import calculate_distribution
# DISTRIBUTION_TESTS_V4_END

# GROUPED_STATISTICS_TESTS_V5_START
from calculator import calculate_grouped_statistics
# GROUPED_STATISTICS_TESTS_V5_END
EXAMPLES = %r
class GeneratedAcceptanceTests(unittest.TestCase):
    def test_reference_cases(self):
        for row in EXAMPLES:
            with self.subTest(row=row):
                actual = Decimal(calculate(row['inputs'])['result'])
                expected = Decimal(str(row['output']))
                self.assertLessEqual(abs(actual-expected), Decimal('1e-12')*max(Decimal(1),abs(expected)))
    def test_schema_rejects_missing_input(self):
        with self.assertRaises(ValueError): calculate({})
    def test_rejects_nonfinite_and_boolean_inputs(self):
        for value in (True, 'NaN', 'Infinity', '1e9999', None):
            sample = dict(EXAMPLES[0]['inputs'])
            sample[next(iter(sample))] = value
            with self.assertRaises(ValueError): calculate(sample)
    # BATCH_TESTS_V2_START
    def test_customer_batch_matches_single_results(self):
        rows=[item['inputs'] for item in EXAMPLES[:3]]
        observed=calculate_batch(rows)
        self.assertEqual(observed['count'],len(rows))
        self.assertEqual(observed['results'],[calculate(item) for item in rows])
    def test_customer_batch_rejects_limits_and_invalid_rows(self):
        for bad in ([],[{}], [{}]*101, None, {}, 'x'):
            with self.assertRaises(ValueError): calculate_batch(bad)
        sample=dict(EXAMPLES[0]['inputs'])
        sample[next(iter(sample))]=True
        with self.assertRaises(ValueError):
            calculate_batch([EXAMPLES[0]['inputs'],sample])
    # BATCH_TESTS_V2_END
    # STATS_TESTS_V3_START
    def test_statistics_match_independent_decimal_reference(self):
        rows=[item['inputs'] for item in EXAMPLES[:3]]
        values=[Decimal(calculate(row)['result']) for row in rows]
        references=[Decimal(str(item['output'])) for item in EXAMPLES[:3]]
        observed=calculate_statistics(rows)
        self.assertEqual(observed['count'],3)
        self.assertEqual(observed['unit'],calculate(rows[0])['unit'])
        with localcontext() as context:
            context.prec=40
            total=sum(values,Decimal(0))
            average=total/Decimal(3)
        self.assertEqual(Decimal(observed['sum']),total)
        self.assertEqual(Decimal(observed['minimum']),min(values))
        self.assertEqual(Decimal(observed['maximum']),max(values))
        self.assertEqual(Decimal(observed['mean']),average)
        for actual,expected in zip(values,references):
            self.assertLessEqual(abs(actual-expected),Decimal('1e-12')*max(Decimal(1),abs(expected)))
    def test_statistics_fail_closed_on_bad_batch(self):
        for bad in ([], [{}], [{}]*101, None, 'broken'):
            with self.assertRaises(ValueError): calculate_statistics(bad)
    # STATS_TESTS_V3_END
    # DISTRIBUTION_TESTS_V4_START
    def test_distribution_quartiles_and_variance_independent_reference(self):
        rows = [item['inputs'] for item in EXAMPLES[:3]]
        values = sorted(Decimal(calculate(row)['result']) for row in rows)
        actual = calculate_distribution(rows)
        self.assertEqual(actual['count'], len(values))
        self.assertEqual(actual['unit'], calculate(rows[0])['unit'])
        with localcontext() as ctx:
            ctx.prec = 50
            mean = sum(values, Decimal(0)) / Decimal(len(values))
            variance = sum(((value - mean)**2 for value in values), Decimal(0)) / Decimal(len(values))
            def q(level):
                pos = Decimal(len(values)-1) * Decimal(level) / Decimal(100)
                low = int(pos)
                weight = pos - Decimal(low)
                return values[low]*(Decimal(1)-weight)+values[min(low+1,len(values)-1)]*weight
            self.assertEqual(Decimal(actual['population_variance']), variance)
            for key,percent in (('p25',25),('median',50),('p75',75)):
                self.assertEqual(Decimal(actual[key]), q(percent))
        self.assertGreaterEqual(Decimal(actual['p75']), Decimal(actual['median']))
        self.assertGreaterEqual(Decimal(actual['median']), Decimal(actual['p25']))
    def test_distribution_singleton_and_invalid_records_fail_closed(self):
        record = EXAMPLES[0]['inputs']
        one = calculate_distribution([record])
        self.assertEqual(Decimal(one['population_variance']), Decimal(0))
        self.assertEqual(one['p25'], one['median'])
        self.assertEqual(one['median'], one['p75'])
        for invalid in ([], [{}], [{}]*101, None, 'broken'):
            with self.assertRaises(ValueError):
                calculate_distribution(invalid)
    # DISTRIBUTION_TESTS_V4_END
    # GROUPED_STATISTICS_TESTS_V5_START
    def test_grouped_statistics_match_independent_decimal_reference(self):
        rows=[item['inputs'] for item in EXAMPLES[:4]]
        group_by=next(iter(rows[0]))
        observed=calculate_grouped_statistics(rows, group_by)
        self.assertEqual(observed['group_by'], group_by)
        self.assertEqual(observed['unit'], calculate(rows[0])['unit'])
        expected={}
        for row in rows:
            key=Decimal(str(row[group_by]))
            expected.setdefault(key, []).append(Decimal(calculate(row)['result']))
        self.assertEqual(len(observed['groups']), len(expected))
        for actual, key in zip(observed['groups'], sorted(expected)):
            values=expected[key]
            self.assertEqual(Decimal(actual['group_value']), key)
            self.assertEqual(actual['count'], len(values))
            self.assertEqual(Decimal(actual['sum']), sum(values, Decimal(0)))
            self.assertEqual(Decimal(actual['minimum']), min(values))
            self.assertEqual(Decimal(actual['maximum']), max(values))
            self.assertEqual(Decimal(actual['mean']), sum(values, Decimal(0))/Decimal(len(values)))
    def test_grouped_statistics_reject_invalid_field_and_batch(self):
        row=EXAMPLES[0]['inputs']
        group_by=next(iter(row))
        for field in ('unknown', None, '', 1):
            with self.assertRaises(ValueError): calculate_grouped_statistics([row], field)
        for records in ([], [{}], [{}]*101, None, 'broken'):
            with self.assertRaises(ValueError): calculate_grouped_statistics(records, group_by)
    # GROUPED_STATISTICS_TESTS_V5_END
''' % examples
    readme = '# '+spec['title']+'\n\n'+spec['problem']+'\n\n'
    readme += 'Method: bounded arithmetic program synthesis; not a general AI invention.\n\n'
    readme += 'Inputs: '+json.dumps(spec['inputs'],ensure_ascii=False)+'\n\n'
    readme += 'Output unit: '+spec['output_unit']+'\n\n'+spec['limitations']+'\n\n'
    readme += 'Run: python calculator.py < example_inputs.json\n\n'
    readme += 'Bounded batch usage: provide a JSON array of 1-100 complete input objects on stdin; invalid entries reject the whole batch.\n\n'
    readme += 'Python API: calculate_statistics(records) and calculate_distribution(records) provide exact-Decimal descriptive summaries, interpolated p25/median/p75, and population variance for 1-100 validated customer rows. calculate_grouped_statistics(records, group_by) provides ordered per-input totals, counts, ranges and means. Descriptions are not predictive risk estimates.\n\n'
    readme += 'Technical prototype; scientific, usability and commercial review remain pending.\n'
    stage = Path(tempfile.mkdtemp(prefix='.candidate-',dir=str(recipes)))
    try:
        for filename, body in {'calculator.py':code,'test_calculator.py':tests,'README.md':readme,
                               'example_inputs.json':json.dumps(examples[0]['inputs'],indent=2)+'\n',
                               'design_request.json':json.dumps(spec,ensure_ascii=False,indent=2)+'\n',
                               'design_receipt.json':json.dumps(provenance,ensure_ascii=False,indent=2)+'\n'}.items():
            (stage/filename).write_text(body,encoding='utf-8')
            os.chmod(str(stage/filename),0o600)
        ast.parse(code); ast.parse(tests)
        if family=='F27':
            create_workbook(stage,spec,tree)
        stage.rename(destination)
    finally:
        if stage.exists():
            import shutil
            shutil.rmtree(str(stage))
    return dict(provenance,created=True)


def seed_requests(root, seed_file):
    if seed_file is None or not Path(seed_file).is_file(): return
    source=read(Path(seed_file))
    seeds=source.get('requests')
    if not isinstance(seeds,list): raise ValueError('DESIGN_SEEDS_INVALID')
    for spec in seeds:
        if not isinstance(spec,dict): raise ValueError('DESIGN_SEED_INVALID')
        file=root/'design-intake'/(digest(spec)+'.json')
        if not file.exists(): save(file,spec)


def enqueue_database_requests(database, root):
    """Import explicit design specs from factory-owned drafts, never DB writes."""
    import sqlite3
    if database is None: return 0
    path=Path(database)
    if path.is_symlink() or not path.is_file(): raise ValueError('DESIGN_DATABASE_UNSAFE')
    imported=0
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=10) as db:
        db.execute('PRAGMA query_only=ON')
        fields={x[1] for x in db.execute('PRAGMA table_info(core_product)')}
        if not {'id','metadata','active','factory_managed'}.issubset(fields):
            raise ValueError('DESIGN_DATABASE_SCHEMA_UNSUPPORTED')
        rows=db.execute('SELECT id,metadata FROM core_product WHERE factory_managed=1 AND active=0 ORDER BY id')
        for ident,raw in rows:
            if not isinstance(raw,str) or len(raw)>MAX_BYTES: continue
            try: meta=json.loads(raw)
            except ValueError: continue
            if not isinstance(meta,dict) or not isinstance(meta.get('factory_design'),dict): continue
            spec=dict(meta['factory_design'],source_product_id=ident)
            target=root/'design-intake'/(digest(spec)+'.json')
            if not target.exists():
                save(target,spec); imported+=1
    return imported


def cycle(root, *, seed_file=None, max_designs=1, database=None, now=None):
    """Fair bounded work per tick, with no lifetime limit on accepted requests."""
    root=Path(root)
    now=time.time() if now is None else now
    if isinstance(max_designs,bool) or not isinstance(max_designs,int) or max_designs < 1:
        raise ValueError('DESIGN_CAPACITY_INVALID')
    private(root/'design-intake'); private(root/'design-state')
    intake_failures=[]
    try:seed_requests(root,seed_file)
    except (ValueError,OSError) as error:
        intake_failures.append({'source':'seed','reason':str(error)[:300]})
    try:imported=enqueue_database_requests(database,root)
    except (ValueError,OSError,sqlite3.Error) as error:
        imported=0
        intake_failures.append({'source':'database','reason':str(error)[:300]})
    actions=[]; blocked=[]; pending=0; attempts=0; deferred=0
    engine_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for request in sorted((root/'design-intake').iterdir()):
        if request.name.startswith('.'): continue
        ticket=root/'design-state'/('blocked-'+digest({'file':request.name,'engine':engine_sha})+'.json')
        prior={}
        charged=False
        sha=None
        try:
            spec=read(request)
            sha=digest(spec)
            ticket=root/'design-state'/(digest({'request':sha,'engine':engine_sha})+'.json')
            if ticket.is_file():
                prior=read(ticket)
                previous_result=prior.get('result',{})
                previous_recipe=previous_result.get('recipe') if isinstance(previous_result,dict) else None
                if prior.get('status')=='design_rework_required':
                    if now < prior.get('retry_at',0):
                        deferred+=1; continue
                elif previous_recipe and (root/'generated-product-recipes'/previous_recipe).is_dir():
                    continue
            if attempts >= max_designs:
                pending+=1; continue
            attempts+=1; charged=True
            result=compile_recipe(spec,root/'generated-product-recipes')
            receipt={'status':'recipe_created' if result['created'] else 'equivalent_program_exists',
                     'request_sha256':sha,'request_file':request.name,'result':result}
            save(ticket,receipt); actions.append(receipt)
        except (ValueError,OSError,ArithmeticError) as error:
            # Keep original request for correction; changed contents yield a new revision.
            # Reading a malformed request also consumes capacity. Every rejected
            # request remains retryable; transient I/O failures cannot retire it.
            if not charged:
                if ticket.is_file():
                    try:prior=read(ticket)
                    except (ValueError,OSError):prior={}
                if now < prior.get('retry_at',0):
                    deferred+=1; continue
                if attempts >= max_designs:
                    pending+=1; continue
                attempts+=1
            number=prior.get('attempt',0)+1
            row={'status':'design_rework_required','request_file':request.name,
                 'reason':str(error)[:300],'attempt':number,'return_to_stage':1,
                 'retry_at':now+min(3600,60*(2**min(number-1,6))),
                 'lifetime_attempt_limit':None}
            save(ticket,row); blocked.append(row)
    result={'schema':'saeit.factory.designer-state.v1','new_recipes':sum(x['result']['created'] for x in actions),
            'requests_processed':attempts,'pending_requests':pending,'deferred_rework_requests':deferred,
            'database_design_requests_imported':imported,'intake_failures':intake_failures,
            'actions':actions,'rework':blocked,'adapter_families_implemented':['F27','F28'],
            'catalog_lifetime_limit':None,'general_ai_invention':False,'commercial_release':False}
    save(root/'designer-state.json',result)
    return result


def recover_recipe(recipe, recipes):
    """Regenerate ONLY compiler-owned programs from their original checked spec.

    Does not repair arbitrary human programs or fabricate missing evidence.
    Tests the regenerated source before retaining and replacing the broken source.
    """
    import importlib.util
    recipes=Path(recipes)
    if not re.fullmatch(r'(?:synth|sheet)_[a-f0-9]{24}',recipe):
        raise ValueError('DESIGN_RECOVERY_NOT_COMPILER_OWNED')
    source=recipes/recipe
    if source.is_symlink() or not source.is_dir():
        raise ValueError('DESIGN_RECOVERY_UNSAFE_SOURCE')
    original=read(source/'design_request.json')
    receipt=read(source/'design_receipt.json')
    if (receipt.get('schema')!='saeit.factory.synthesis-receipt.v1'
            or receipt.get('request_sha256')!=digest(original)
            or receipt.get('recipe')!=recipe):
        raise ValueError('DESIGN_RECOVERY_PROVENANCE_MISMATCH')
    with tempfile.TemporaryDirectory(prefix='.rebuild-',dir=str(recipes)) as td:
        rebuilt=compile_recipe(original,Path(td))
        if rebuilt['recipe']!=recipe:
            raise ValueError('DESIGN_RECOVERY_IDENTITY_MISMATCH')
        script=Path(__file__).resolve().parent/'factory_product_maker.py'
        spec=importlib.util.spec_from_file_location('saeit_rebuild_qa',script)
        maker=importlib.util.module_from_spec(spec); spec.loader.exec_module(maker)
        measurements={}
        candidate=Path(td)/recipe
        maker.verify_recipe(candidate,evidence=measurements)
        retained=recipes.parent/'generated-source-revisions'
        private(retained)
        archive=Path(tempfile.mkdtemp(prefix=recipe+'-',dir=str(retained)))
        archive.rmdir()
        source.rename(archive)
        try: candidate.rename(source)
        except OSError:
            archive.rename(source)
            raise
    return {'schema':'saeit.factory.source-recovery.v1','recipe':recipe,
            'action':'regenerated_from_original_validated_spec',
            'retained_broken_source':str(archive),'qa_measurements':measurements,
            'commercial_release':False}



def evolve_recipe(recipe, recipes):
    """Make a genuine, QA-tested private revision of a compiler-owned product.

    Never patch arbitrary authored products.  A verified original design request
    is rebuilt with the improved compiler, its complete tests execute before
    replacing any source, and the exact previous source directory is retained.
    This is a functional engineering improvement, NOT a 1000-point approval.
    """
    import importlib.util
    recipes=Path(recipes)
    if recipes.is_symlink() or not recipes.is_dir():
        raise ValueError('EVOLUTION_ROOT_UNSAFE')
    if not re.fullmatch(r'(?:synth|sheet)_[a-f0-9]{24}',recipe):
        raise ValueError('EVOLUTION_REQUIRES_COMPILER_OWNED_RECIPE')
    source=recipes/recipe
    if source.is_symlink() or not source.is_dir():
        raise ValueError('EVOLUTION_SOURCE_UNSAFE')
    request=read(source/'design_request.json')
    receipt=read(source/'design_receipt.json')
    if (receipt.get('schema')!='saeit.factory.synthesis-receipt.v1'
            or receipt.get('request_sha256')!=digest(request)
            or receipt.get('recipe')!=recipe
            or receipt.get('family_id')!=request.get('family_id')):
        raise ValueError('EVOLUTION_PROVENANCE_MISMATCH')
    calculator=source/'calculator.py'
    if calculator.is_symlink() or not calculator.is_file() or calculator.stat().st_size>MAX_BYTES:
        raise ValueError('EVOLUTION_SOURCE_NOT_COMPILER_OWNED')
    prior_code=calculator.read_text(encoding='utf8')
    if not prior_code.startswith('"""Generated deterministic arithmetic planning tool;'):
        raise ValueError('EVOLUTION_SOURCE_NOT_COMPILER_OWNED')
    if ('# GROUPED_STATISTICS_API_V5_START' in prior_code
            and receipt.get('generator_capability_revision')=='verified-grouped-statistics-v5'):
        return {'schema':'saeit.factory.source-evolution.v1',
                'recipe':recipe,'changed':False,
                'reason':'already_evolved','commercial_release':False}
    maker_path=Path(__file__).resolve().parent/'factory_product_maker.py'
    spec=importlib.util.spec_from_file_location('saeit_evolution_manufacturer',maker_path)
    maker=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(maker)
    old_name,old_files=maker.inspect_recipe(source)
    old_digest=maker.source_digest(source,old_files)
    maker.verify_recipe(source)
    # A new compiler cannot erase unspecified authored extensions or symlinks.
    with tempfile.TemporaryDirectory(prefix='.evolution-',dir=str(recipes)) as staging:
        generated=compile_recipe(request,Path(staging))
        if generated['recipe']!=recipe:
            raise ValueError('EVOLUTION_FUNCTIONAL_IDENTITY_CHANGED')
        candidate=Path(staging)/recipe
        new_name,new_files=maker.inspect_recipe(candidate)
        if set(old_files)!=set(new_files):
            raise ValueError('EVOLUTION_FILESET_CHANGE_REQUIRES_REVIEW')
        new_digest=maker.source_digest(candidate,new_files)
        if old_digest==new_digest:
            return {'schema':'saeit.factory.source-evolution.v1',
                    'recipe':recipe,'changed':False,
                    'reason':'identical_compiler_output','commercial_release':False}
        measurements={}
        maker.verify_recipe(candidate,evidence=measurements,minimum_tests=5)
        # Never overwrite the prior source without recording the exact original.
        if maker.source_digest(source,old_files)!=old_digest:
            raise ValueError('EVOLUTION_SOURCE_CHANGED_BEFORE_CUTOVER')
        revisions=recipes.parent/'generated-source-revisions'
        private(revisions)
        saved=Path(tempfile.mkdtemp(prefix=recipe+'-evolved-',dir=str(revisions)))
        saved.rmdir()
        source.rename(saved)
        try:
            candidate.rename(source)
        except OSError:
            saved.rename(source)
            raise
    return {'schema':'saeit.factory.source-evolution.v1',
            'recipe':recipe,'changed':True,
            'previous_source_sha256':old_digest,
            'revised_source_sha256':new_digest,
            'previous_source_retained':str(saved),
            'measured_acceptance':measurements,
            'implemented_feature':'verified_decimal_grouped_customer_batch_statistics_v5',
            'independent_specialist_approval_verified':False,
            'quality_1000_certified':False,'commercial_release':False}


def create_workbook(folder,spec,tree):
    """Construct an actual protected XLSX, not a file with a changed extension.

    Rational reference evaluation tests serialized Excel formulas independently
    of the generated Decimal program. Office recalculation and usability remain
    separate acceptance requirements before any commercial approval.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Protection,Font,PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    def excel(node):
        if isinstance(node,int):return 'B'+str(node+2)
        return '('+excel(node[1])+node[0]+excel(node[2])+')'
    book=Workbook();sheet=book.active;sheet.title='Calculator'
    sheet.append(['Parameter','Value','Unit'])
    for field in spec['inputs']:
        row=sheet.max_row+1
        sheet.append([field['name'],float(spec['training_examples'][0]['inputs'][field['name']]),field['unit']])
        sheet.cell(row,2).protection=Protection(locked=False)
        rule=DataValidation(type='whole' if field.get('integral') else 'decimal',operator='between',formula1=field.get('minimum',-1e12),
                            formula2=field.get('maximum',1e12),allow_blank=False)
        rule.showErrorMessage=True;rule.error='Use the documented finite input domain.'
        sheet.add_data_validation(rule);rule.add(sheet.cell(row,2))
    output=sheet.max_row+2
    sheet.cell(output,1,'Result');sheet.cell(output,2,'='+excel(tree));sheet.cell(output,3,spec['output_unit'])
    sheet.freeze_panes='B2';sheet.protection.sheet=True
    for cell in sheet[1]:cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='17365D')
    for name,width in [('A',35),('B',24),('C',30)]:sheet.column_dimensions[name].width=width
    guide=book.create_sheet('Read me');guide.append([spec['title']]);guide.append([spec['problem']]);guide.append([spec['limitations']])
    guide.append(['Technical mathematical prototype; Office recalculation and domain review pending.'])
    guide.column_dimensions['A'].width=100
    book.save(folder/'calculator.xlsx')
    acceptance = """import ast
from fractions import Fraction
from pathlib import Path
import unittest
from openpyxl import load_workbook
ROWS=%r
NAMES=%r
OUTPUT_ROW=%r
class WorkbookIndependentTests(unittest.TestCase):
    def test_serialized_formula_against_rational_reference(self):
        book=load_workbook(Path(__file__).with_name('calculator.xlsx'))
        sheet=book['Calculator'];formula=sheet.cell(OUTPUT_ROW,2).value
        expression=ast.parse(formula[1:],mode='eval')
        def evaluate(node,values):
            if isinstance(node,ast.Expression):return evaluate(node.body,values)
            if isinstance(node,ast.Name):return values[node.id]
            if not isinstance(node,ast.BinOp):raise ValueError('UNSAFE_EXCEL_FORMULA')
            a=evaluate(node.left,values);b=evaluate(node.right,values)
            if isinstance(node.op,ast.Add):return a+b
            if isinstance(node.op,ast.Sub):return a-b
            if isinstance(node.op,ast.Mult):return a*b
            if isinstance(node.op,ast.Div):return a/b
            raise ValueError('UNSAFE_EXCEL_OPERATOR')
        for row in ROWS:
            values={'B'+str(i+2):Fraction(str(row['inputs'][name])) for i,name in enumerate(NAMES)}
            expected=Fraction(str(row['output']));actual=evaluate(expression,values)
            self.assertLessEqual(abs(actual-expected),Fraction('1e-12')*max(1,abs(expected)))
        self.assertTrue(sheet.protection.sheet)
        self.assertEqual(sheet.freeze_panes,'B2')
        self.assertTrue(sheet.cell(OUTPUT_ROW,2).protection.locked)
        self.assertEqual(len(sheet.data_validations.dataValidation),len(NAMES))
""" % (spec['training_examples']+spec['acceptance_examples'],[x['name'] for x in spec['inputs']],output)
    (folder/'test_workbook.py').write_text(acceptance,encoding='utf8')
