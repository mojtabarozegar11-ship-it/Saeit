"""Execute the exact management-command method AST with read-only fake QuerySets."""
import ast
import json
from pathlib import Path
import unittest
from core.tron_tx_conflict_audit import summarize_tron_conflicts

TX = 'a'*64
TX2 = 'b'*64

class Query:
    def __init__(self, rows, log): self.rows, self.log = rows, log
    def filter(self, **kw):
        self.log.append(('filter',kw))
        return self
    def order_by(self, *fields):
        self.log.append(('order_by',fields))
        return self
    def values(self,*fields):
        self.log.append(('values',fields))
        return self
    def __getitem__(self, sl):
        self.log.append(('slice',sl.start,sl.stop,sl.step))
        return self.rows[sl]

class Model:
    def __init__(self, rows, log): self.objects=Query(rows, log)

class Stdout:
    def __init__(self): self.messages=[]
    def write(self, item): self.messages.append(item)

class BaseCommand:
    def __init__(self): self.stdout=Stdout()

class NativeTronConflictCommandTests(unittest.TestCase):
    def command(self,events,credits):
        f=Path(__file__).resolve().parents[1] / 'core' / 'management' / 'commands' / 'tron_conflict_audit.py'
        t=ast.parse(f.read_text())
        k=[node for node in t.body if isinstance(node,ast.ClassDef) and node.name=='Command']
        self.assertEqual(len(k),1)
        log=[]
        namespace={'BaseCommand':BaseCommand,'PaymentWebhookEvent':Model(events,log),
            'LedgerEntry':Model(credits,log),'summarize_tron_conflicts':summarize_tron_conflicts,'json':json}
        exec(compile(ast.fix_missing_locations(ast.Module(body=k,type_ignores=[])),str(f),'exec'),namespace)
        return namespace['Command'](),log
    def run_cmd(self,events,credits,limit=5000):
        c,log=self.command(events,credits);c.handle(limit=limit)
        self.assertEqual(len(c.stdout.messages),1)
        line=c.stdout.messages[0]
        self.assertTrue(line.startswith('TRON_CONFLICT_AUDIT='))
        return json.loads(line.split('=',1)[1]),log
    def test_clean_writes_only_stdout(self):
        out, log=self.run_cmd([{'event_id':TX,'provider':'new','status':'processed'}],[{'reference':'tron-mainnet:'+TX}])
        self.assertTrue(out['no_conflicts_in_bounded_snapshot'])
        self.assertTrue(all(x[0] in {'filter','order_by','values','slice'} for x in log))
    def test_reject_uppercase_duplicate_event(self):
        out,_=self.run_cmd([{'event_id':TX,'provider':'new','status':'processed'},
                            {'event_id':TX.upper(),'provider':'old','status':'processed'}],[{'reference':'tron-mainnet:'+TX}])
        self.assertEqual(out['finding_count'],1)
    def test_no_raw_txid_emitted(self):
        out,_=self.run_cmd([{'event_id':TX,'provider':'new','status':'processed'}],[])
        self.assertNotIn(TX,json.dumps(out))
    def test_bounded_query_slices(self):
        _,log=self.run_cmd([],[],limit=3)
        self.assertEqual([a[2] for a in log if a[0]=='slice'],[4,4])
    def test_truncation_blocks_clean_status(self):
        events=[{'event_id':(format(n,'064x')),'provider':'new','status':'processed'} for n in range(1,5)]
        out,_=self.run_cmd(events,[],limit=2)
        self.assertFalse(out['complete'])
        self.assertFalse(out['no_conflicts_in_bounded_snapshot'])
        self.assertEqual(out['scanned_events'],2)
    def test_live_runtime_stays_unverified(self):
        out,_=self.run_cmd([],[])
        self.assertIs(out['live_runtime_verified'],False)
    def test_payment_safety_never_asserted(self):
        out,_=self.run_cmd([],[])
        self.assertIs(out['production_payment_safe'],False)
    def test_reject_zero_limit(self):
        cmd,_=self.command([],[])
        with self.assertRaises(ValueError):cmd.handle(limit=0)
    def test_reject_bool_limit(self):
        cmd,_=self.command([],[])
        with self.assertRaises(ValueError):cmd.handle(limit=True)
    def test_reject_overlimit(self):
        cmd,_=self.command([],[])
        with self.assertRaises(ValueError):cmd.handle(limit=20001)
    def test_only_relevant_query_fields(self):
        _,log=self.run_cmd([],[])
        names=[x[1] for x in log if x[0]=='values']
        self.assertEqual(names,[('event_id','provider','status'),('reference',)])

if __name__=='__main__':unittest.main()
