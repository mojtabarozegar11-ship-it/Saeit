"""Transactional order store; no withdrawal or automatic allocation operations."""
import hashlib, hmac, json, os, re, secrets, sqlite3, time
from contextlib import contextmanager
from pathlib import Path

class Rejected(ValueError): pass

def password_hash(password, salt=None):
    if not 12 <= len(password) <= 200: raise Rejected('password_length')
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260000).hex()
    return salt + ':' + digest

def password_valid(password, stored):
    try: return hmac.compare_digest(password_hash(password, stored.split(':')[0]), stored)
    except (ValueError, TypeError): return False

class Store:
    def __init__(self, path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.tx() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS orders(
              id TEXT PRIMARY KEY, nonce TEXT UNIQUE NOT NULL, email TEXT NOT NULL,
              password TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>=10000),
              artifact TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'created',
              authority TEXT UNIQUE, reference TEXT UNIQUE, created REAL NOT NULL,
              paid REAL, downloads INTEGER NOT NULL DEFAULT 0, source TEXT NOT NULL,
              terms TEXT NOT NULL, refund_amount INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, name TEXT NOT NULL,
              order_id TEXT, source TEXT, at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS support(id TEXT PRIMARY KEY, order_id TEXT NOT NULL,
              kind TEXT NOT NULL, body TEXT NOT NULL, response TEXT NOT NULL DEFAULT '',
              created REAL NOT NULL, state TEXT NOT NULL DEFAULT 'open');
            CREATE TABLE IF NOT EXISTS limits(k TEXT NOT NULL, at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS limits_key ON limits(k,at);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, action TEXT NOT NULL,
              order_id TEXT, detail TEXT NOT NULL, at REAL NOT NULL);
            CREATE TRIGGER IF NOT EXISTS no_paid_downgrade BEFORE UPDATE OF state ON orders
              WHEN OLD.state='paid' AND NEW.state NOT IN ('paid','refunded')
              BEGIN SELECT RAISE(ABORT,'paid_order_immutable'); END;
            CREATE TRIGGER IF NOT EXISTS no_order_value_change BEFORE UPDATE OF amount,artifact ON orders
              BEGIN SELECT RAISE(ABORT,'order_value_immutable'); END;
            ''')
        os.chmod(self.path, 0o600)

    @contextmanager
    def tx(self):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys=ON'); db.execute('BEGIN IMMEDIATE')
            yield db; db.commit()
        except BaseException: db.rollback(); raise
        finally: db.close()

    def event(self, name, event_id, order_id='', source='direct'):
        if name not in {'visit','checkout','payment_requested','payment_verified','download','feedback','payment_error'}: raise Rejected('event_type')
        with self.tx() as db:
            db.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?,?)', (event_id,name,order_id,source,time.time()))

    def rate(self, key, count=10, window=900):
        now=time.time()
        with self.tx() as db:
            db.execute('DELETE FROM limits WHERE at<?',(now-86400,))
            if db.execute('SELECT COUNT(*) FROM limits WHERE k=? AND at>?',(key,now-window)).fetchone()[0]>=count: return False
            db.execute('INSERT INTO limits VALUES(?,?)',(key,now)); return True

    def create(self, email, password, amount, artifact, nonce, source, terms):
        email=email.strip().lower()
        if len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email): raise Rejected('invalid_email')
        if type(amount) is not int or not 10000<=amount<=1000000000: raise Rejected('invalid_amount')
        if not re.fullmatch('[a-f0-9]{64}',artifact): raise Rejected('artifact_hash')
        hashed=password_hash(password)
        with self.tx() as db:
            old=db.execute('SELECT * FROM orders WHERE nonce=?',(nonce,)).fetchone()
            if old:
                if old['email']!=email or not password_valid(password,old['password']): raise Rejected('duplicate_order_mismatch')
                return dict(old)
            oid=secrets.token_hex(16)
            db.execute('INSERT INTO orders(id,nonce,email,password,amount,artifact,created,source,terms) VALUES(?,?,?,?,?,?,?,?,?)',
                (oid,nonce,email,hashed,amount,artifact,time.time(),source[:100],terms))
            return dict(db.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone())

    def get(self, oid):
        with self.tx() as db:
            r=db.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
            return dict(r) if r else None

    def by_authority(self, authority):
        with self.tx() as db:
            r=db.execute('SELECT * FROM orders WHERE authority=?',(authority,)).fetchone()
            return dict(r) if r else None

    def authenticate(self, oid, email, password):
        r=self.get(oid)
        return bool(r and hmac.compare_digest(r['email'],email.strip().lower()) and password_valid(password,r['password']))

    def claim_request(self, oid):
        with self.tx() as db:
            return db.execute("UPDATE orders SET state='requesting' WHERE id=? AND state='created'",(oid,)).rowcount==1

    def attach(self, oid, authority):
        if not re.fullmatch('[A-Za-z0-9-]{30,64}',authority): raise Rejected('bad_authority')
        with self.tx() as db:
            if not db.execute("UPDATE orders SET authority=?,state='awaiting_payment' WHERE id=? AND state='requesting'",(authority,oid)).rowcount: raise Rejected('invalid_state')

    def uncertain(self, oid):
        with self.tx() as db:
            db.execute("UPDATE orders SET state='request_unknown' WHERE id=? AND state='requesting'",(oid,))
            db.execute('INSERT INTO audit(action,order_id,detail,at) VALUES(?,?,?,?)',('request_unknown',oid,'no automatic retry',time.time()))

    def verified(self, oid, authority, amount, reference, code):
        if code not in (100,101) or not re.fullmatch('[0-9]{1,40}',str(reference)) or int(reference)<=0: raise Rejected('verification_failed')
        with self.tx() as db:
            r=db.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
            if not r or r['authority']!=authority or r['amount']!=amount: raise Rejected('payment_mismatch')
            if r['state']=='paid':
                if r['reference']!=str(reference): raise Rejected('reference_mismatch')
                return False
            if r['state']!='awaiting_payment': raise Rejected('invalid_state')
            if db.execute('SELECT id FROM orders WHERE reference=? AND id!=?',(str(reference),oid)).fetchone(): raise Rejected('reference_already_used')
            db.execute("UPDATE orders SET state='paid',reference=?,paid=? WHERE id=?",(str(reference),time.time(),oid))
            db.execute('INSERT INTO events VALUES(?,?,?,?,?)',('paid:'+oid,'payment_verified',oid,r['source'],time.time()))
            db.execute('INSERT INTO audit(action,order_id,detail,at) VALUES(?,?,?,?)',('verified',oid,'server verification; IRR='+str(amount),time.time()))
            return True

    def download(self, oid, artifact):
        with self.tx() as db:
            r=db.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
            if not r or r['state']!='paid' or r['artifact']!=artifact: raise Rejected('not_entitled')
            if r['downloads']>=20 or time.time()-r['paid']>365*86400: raise Rejected('download_limit_contact_support')
            db.execute('UPDATE orders SET downloads=downloads+1 WHERE id=?',(oid,))
            db.execute('INSERT INTO events VALUES(?,?,?,?,?)',(secrets.token_hex(16),'download',oid,r['source'],time.time()))

    def ticket(self, oid, kind, body):
        if kind not in ('support','feedback','refund') or not 10<=len(body.strip())<=3000: raise Rejected('invalid_ticket')
        if not self.get(oid): raise Rejected('unknown_order')
        with self.tx() as db:
            if db.execute('SELECT COUNT(*) FROM support WHERE order_id=? AND created>?',(oid,time.time()-86400)).fetchone()[0]>=5: raise Rejected('ticket_limit')
            tid=secrets.token_hex(12)
            db.execute('INSERT INTO support(id,order_id,kind,body,created) VALUES(?,?,?,?,?)',(tid,oid,kind,body.strip(),time.time()))
            return tid

    def tickets(self, oid=None):
        with self.tx() as db:
            if oid: rows=db.execute('SELECT * FROM support WHERE order_id=? ORDER BY created DESC LIMIT 100',(oid,))
            else: rows=db.execute('SELECT * FROM support ORDER BY created DESC LIMIT 100')
            return [dict(r) for r in rows]

    def respond(self, tid, response):
        if not 5<=len(response.strip())<=3000: raise Rejected('invalid_response')
        with self.tx() as db:
            if not db.execute("UPDATE support SET response=?,state='answered' WHERE id=?",(response.strip(),tid)).rowcount: raise Rejected('unknown_ticket')
            db.execute('INSERT INTO audit(action,detail,at) VALUES(?,?,?)',('support_response',tid,time.time()))

    def record_external_refund(self, oid, amount, evidence):
        # Accounting only. No gateway reversal, transfer or bank API exists here.
        if not evidence.strip() or len(evidence)>300: raise Rejected('refund_evidence_required')
        with self.tx() as db:
            r=db.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
            if not r or r['state']!='paid' or amount!=r['amount']: raise Rejected('full_verified_refund_only')
            db.execute("UPDATE orders SET state='refunded',refund_amount=? WHERE id=?",(amount,oid))
            db.execute('INSERT INTO audit(action,order_id,detail,at) VALUES(?,?,?,?)',('human_external_refund',oid,evidence,time.time()))

    def metrics(self):
        with self.tx() as db:
            counts={r[0]:r[1] for r in db.execute('SELECT name,COUNT(*) FROM events GROUP BY name')}
            money=db.execute("SELECT COALESCE(SUM(amount),0),COALESCE(SUM(refund_amount),0),COUNT(*) FROM orders WHERE paid IS NOT NULL").fetchone()
            sources=[dict(r) for r in db.execute("SELECT source,COUNT(*) AS orders,SUM(CASE WHEN paid IS NOT NULL THEN 1 ELSE 0 END) AS paid_orders, SUM(CASE WHEN paid IS NOT NULL THEN amount-refund_amount ELSE 0 END) AS collected_irr FROM orders GROUP BY source")]
            return {'events':counts,'gross_collected_irr':money[0],'refunds_irr':money[1],'collected_after_refunds_irr':money[0]-money[1],'paid_orders':money[2],'sources':sources,'profit':None,'net_distributable_revenue':None,'note':'Collected revenue is not profit or distributable revenue. No 90/9/1 allocation without verified deductions.'}
