"""Aquisição simulada, validação por massa e adaptador SAP local transacional."""
import json
import math
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

UNCONFIRMED = 'Responsável não confirmado — movimentação pendente de atribuição.'
EMPLOYEES = {'001': 'João', '002': 'Ana', '003': 'Carlos'}


def now():
    return datetime.now(timezone.utc).isoformat()


class System:
    def __init__(self, path='data/smartbins.db'):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS materials (
          code TEXT PRIMARY KEY, name TEXT, description TEXT, category TEXT,
          unit TEXT, unit_weight REAL, bin TEXT UNIQUE, location TEXT,
          initial_qty INTEGER, tare REAL, minimum INTEGER, sensor TEXT UNIQUE,
          tolerance REAL, threshold REAL, photo BLOB, stock INTEGER,
          physical REAL, baseline REAL, connected INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS events (
          id TEXT PRIMARY KEY, time TEXT, material TEXT, payload TEXT,
          status TEXT, error TEXT, delta REAL, quantity INTEGER, kind TEXT,
          employee TEXT, confidence TEXT, document TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS presence (
          employee TEXT PRIMARY KEY, zone TEXT, confidence REAL, time TEXT);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value INTEGER);
        INSERT OR IGNORE INTO settings VALUES ('sap_online',1);
        ''')
        if not self.materials():
            self.seed()

    def seed(self):
        for code, name, weight, qty, box, minimum in [
            ('MAT-0001','Parafuso M4',2.,100,'CX-001',20),
            ('MAT-0002','Arruela metálica pequena',.1,200,'CX-002',40)]:
            self.db.execute('INSERT INTO materials VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (code,name,'Peça ilustrativa; massa fictícia editável','Fixadores','UN',weight,
                 box,'Zona A' if box=='CX-001' else 'Zona B',qty,50.,minimum,
                 'HX711-'+box,.02 if weight==.1 else .1,
                 .04 if weight==.1 else .2,None,qty,qty*weight+50,qty*weight+50,1))
        self.db.commit()

    def reset(self):
        with self.db:
            for table in ('events','presence','materials'):
                self.db.execute('DELETE FROM '+table)
            self.db.execute("UPDATE settings SET value=1 WHERE key='sap_online'")
        self.seed()

    def materials(self):
        return [dict(r) for r in self.db.execute('SELECT * FROM materials ORDER BY code')]

    def material(self, code):
        row = self.db.execute('SELECT * FROM materials WHERE code=?',(code,)).fetchone()
        if row is None:
            raise ValueError('Material não cadastrado')
        return dict(row)

    def events(self):
        return [dict(r) for r in self.db.execute('SELECT * FROM events ORDER BY time DESC')]

    def online(self):
        return bool(self.db.execute("SELECT value FROM settings WHERE key='sap_online'").fetchone()[0])

    def set_online(self, value):
        with self.db:
            self.db.execute("UPDATE settings SET value=? WHERE key='sap_online'",(int(value),))

    def set_connected(self, code, value):
        with self.db:
            self.db.execute('UPDATE materials SET connected=? WHERE code=?',(int(value),code))

    def presence(self, employee, zone, confidence=.99):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO presence VALUES (?,?,?,?)',
                            (employee,zone,confidence,now()))

    def people(self):
        return [dict(r) for r in self.db.execute('SELECT * FROM presence')]

    def clear_people(self):
        with self.db:
            self.db.execute('DELETE FROM presence')

    def responsible(self, zone):
        # Presença simulada expira após cinco minutos; confiança mínima de 95%.
        rows = [r for r in self.people() if r['zone']==zone and
                (datetime.now(timezone.utc)-datetime.fromisoformat(r['time'])).total_seconds()<300]
        if len(rows)==1 and rows[0]['confidence']>=.95:
            return EMPLOYEES[rows[0]['employee']], 'Alta — presença simulada única'
        return UNCONFIRMED, 'Não confirmada'

    def add_material(self, code, name, box, sensor, location, weight, qty, tare, minimum, tolerance, threshold):
        if not all(str(v).strip() for v in (code,name,box,sensor,location)):
            raise ValueError('Preencha todos os identificadores e a localização')
        if (not all(math.isfinite(v) for v in (weight,tare,tolerance,threshold)) or
            weight<=0 or tare<0 or qty<0 or minimum<0 or
            not 0<tolerance<weight/2 or not 0<threshold<=weight):
            raise ValueError('Calibração inválida: tolerância > 0 e < metade do peso unitário; limite > 0 e ≤ peso unitário')
        with self.db:
            self.db.execute('INSERT INTO materials VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (code,name,'Material cadastrado pelo usuário','Geral','UN',weight,box,location,
                 qty,tare,minimum,sensor,tolerance,threshold,None,qty,qty*weight+tare,qty*weight+tare,1))

    def save_material(self, code, fields):
        allowed = {'name','description','category','unit','unit_weight','location','tare',
                   'minimum','tolerance','threshold','photo','bin','sensor','initial_qty'}
        if not set(fields)<=allowed:
            raise ValueError('Campo inválido')
        m = self.material(code) | fields
        if (not math.isfinite(m['unit_weight']) or m['unit_weight']<=0 or
            not 0<m['tolerance']<m['unit_weight']/2 or
            not 0<m['threshold']<=m['unit_weight'] or m['tare']<0 or
            m['initial_qty']<0 or m['minimum']<0):
            raise ValueError('Exija peso > 0, tolerância < metade do peso unitário e limite entre 0 e o peso unitário.')
        calibration = {'unit_weight','tare','initial_qty','bin','sensor','tolerance','threshold'}
        if any(m[k]!=self.material(code)[k] for k in calibration):
            if self.events():
                raise ValueError('Restaure a demonstração antes de alterar calibração, saldo inicial ou identificação. Histórico preservado.')
            fields |= {'stock':m['initial_qty'], 'physical':m['tare']+m['initial_qty']*m['unit_weight'],
                       'baseline':m['tare']+m['initial_qty']*m['unit_weight']}
        with self.db:
            self.db.execute('UPDATE materials SET '+','.join(k+'=?' for k in fields)+' WHERE code=?',
                            (*fields.values(),code))

    def simulate(self, code, units=0, unstable=False, incompatible=False):
        """Unidades existem apenas no atuador físico; o JSON contém exclusivamente massas."""
        m = self.material(code)
        if not m['connected']:
            raise ValueError('ESP32 desconectado. Reconecte antes da aquisição.')
        target = m['physical'] + units*m['unit_weight']
        if incompatible:
            target += m['unit_weight']*.45
        if target < m['tare']-1e-9:
            raise ValueError('A operação física retiraria mais peças que as existentes.')
        t = m['tolerance']
        readings = [target+t*4,target-t*3,target+t*.2,target-t*.2,target]
        if unstable:
            readings = [target+t*4,target-t*4,target+t*4,target-t*4,target+t*4]
        stable = max(readings[-3:])-min(readings[-3:]) <= t
        with self.db:
            self.db.execute('UPDATE materials SET physical=? WHERE code=?',(target,code))
        payload = dict(event_id=str(uuid.uuid4()), sensor_id=m['sensor'], bin_id=m['bin'],
                       timestamp=now(), previous_weight=m['baseline'], current_weight=readings[-1],
                       stable=stable, readings=readings)
        self.receive(payload)
        return payload

    def receive(self, payload):
        """Middleware: valida origem, estabilidade, continuidade e integralidade da massa."""
        eid = payload['event_id']
        if self.db.execute('SELECT 1 FROM events WHERE id=?',(eid,)).fetchone():
            return # Reentrega idempotente, inclusive após recuperação do SAP.
        m = next((m for m in self.materials() if m['bin']==payload['bin_id']),None)
        error = ''
        quantity, delta, kind = 0, 0., ''
        person, confidence = self.responsible(m['location']) if m else (UNCONFIRMED,'Não confirmada')
        try:
            if not m or payload['sensor_id']!=m['sensor']:
                raise ValueError('Caixa ou sensor não cadastrado')
            previous, current = float(payload['previous_weight']), float(payload['current_weight'])
            readings = payload['readings']
            if not all(math.isfinite(float(x)) for x in [previous,current,*readings]):
                raise ValueError('Massa não finita')
            if (payload['stable'] is not True or len(readings)<3 or
                max(readings[-3:])-min(readings[-3:])>m['tolerance'] or
                abs(current-readings[-1])>1e-9):
                raise ValueError('Leitura instável ou incompatível com as amostras')
            if abs(previous-m['baseline'])>1e-8:
                raise ValueError('Referência anterior divergente; requer conciliação')
            delta = current-previous
            if abs(delta)<m['threshold']:
                status = 'IGNORADO'
            else:
                quantity = round(abs(delta)/m['unit_weight'])
                if quantity<1 or abs(abs(delta)-quantity*m['unit_weight'])>m['tolerance']+1e-9:
                    raise ValueError('Massa incompatível com múltiplo do peso unitário')
                kind = 'ENTRADA' if delta>0 else 'SAÍDA'
                if current<m['tare']-m['tolerance']:
                    raise ValueError('Saldo negativo não permitido')
                status = 'PENDENTE SAP'
        except (ValueError,TypeError,KeyError) as exc:
            status,error = 'PENDENTE VALIDAÇÃO',str(exc)
        with self.db:
            self.db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                (eid,payload.get('timestamp',now()),m['code'] if m else '',json.dumps(payload),
                 status,error,delta,quantity,kind,person,confidence,None))
            if status=='PENDENTE SAP':
                self.db.execute('UPDATE materials SET baseline=? WHERE code=?',
                                (payload['current_weight'],m['code']))
        self.retry()

    def retry(self):
        """Adaptador SAP simulado: documento e saldo na mesma transação SQLite."""
        if not self.online():
            return
        for event in reversed(self.events()):
            if event['status']!='PENDENTE SAP':
                continue
            with self.db:
                e = self.db.execute('SELECT * FROM events WHERE id=?',(event['id'],)).fetchone()
                if e['document'] or e['status']!='PENDENTE SAP':
                    continue
                m = self.material(e['material'])
                balance = m['stock']+(e['quantity'] if e['kind']=='ENTRADA' else -e['quantity'])
                if balance<0:
                    self.db.execute("UPDATE events SET status='PENDENTE VALIDAÇÃO', error='Saldo SAP insuficiente' WHERE id=?",(e['id'],))
                    continue
                document = 'SIM-'+uuid.uuid4().hex[:12].upper()
                self.db.execute('UPDATE materials SET stock=? WHERE code=?',(balance,m['code']))
                self.db.execute("UPDATE events SET status='REGISTRADO',document=?,error='' WHERE id=?",(document,e['id']))

    def scenario(self, letter):
        """Cada roteiro começa em uma base restaurada para resultados reprodutíveis."""
        self.reset()
        self.presence('001','Zona A')
        self.presence('002','Zona B')
        if letter=='A':
            return self.simulate('MAT-0001',-5)
        if letter=='B':
            return self.simulate('MAT-0002',20)
        if letter=='C':
            return self.simulate('MAT-0001',incompatible=True)
        if letter=='D':
            self.set_online(False)
            return self.simulate('MAT-0001',-5)
        if letter=='E':
            self.presence('003','Zona A')
            return self.simulate('MAT-0001',-5)
        raise ValueError('Cenário inexistente')
