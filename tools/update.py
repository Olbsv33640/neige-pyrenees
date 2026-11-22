# Actualisation des données « Neige Pyrénées » : météo/neige (Open-Meteo), cols, webcams (Pyreneige).
# Usage : python3 update.py <dossier_du_site>   (le dossier contient data/ et cams/)
# Écrit data/meteo.json, data/routes.json, data/cams.json, cams/*.jpg, data/live.json
# puis affiche la liste des fichiers modifiés (une ligne par fichier) sous "FICHIERS:".
import json, sys, os, re, time, html, urllib.parse, urllib.request, urllib.error, concurrent.futures as cf
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

SITE = sys.argv[1] if len(sys.argv) > 1 else '.'
DATA = os.path.join(SITE, 'data'); CAMS = os.path.join(SITE, 'cams')
os.makedirs(DATA, exist_ok=True); os.makedirs(CAMS, exist_ok=True)
TZ = ZoneInfo('Europe/Paris')
NOWDT = datetime.now(TZ)
NOW = NOWDT.strftime('%Y-%m-%dT%H:00')
STAMP = NOWDT.strftime('%Y-%m-%dT%H:%M')
CHANGED = []
UA = 'Mozilla/5.0 (X11; Linux x86_64) NeigePyrenees/1.1'

# lat, lon, alt pied, alt sommet
ST = {"luz-ardiden":[42.88579,-0.07007,1720,2450],"cauterets":[42.88382,-0.145445,1850,2415],"grand-tourmalet":[42.90234,0.12821,1400,2500],"pic-du-midi":[42.92401,0.166005,1800,2877],"piau-engaly":[42.77664,0.16119,1420,2600],"saint-lary":[42.8309,0.26275,1700,2515],"peyragudes":[42.779725,0.447625,1600,2400],"val-louron":[42.783025,0.382905,1450,2150],"gavarnie":[42.7215,-0.03952,1850,2400],"hautacam":[42.97055,0.001815,1500,1800],"val-dazun":[42.946,-0.232,1350,1600],"nistos":[42.95,0.47,1550,1800],"superbagneres":[42.773005,0.566035,1440,2260],"le-mourtis":[42.905175,0.771715,1380,1860],"guzet":[42.772265,1.30564,1100,2100],"goulier":[42.73617,1.518425,1500,1800],"beille":[42.709435,1.708135,1800,2000],"ax-3-domaines":[42.687,1.811125,1400,2400],"ascou":[42.727665,1.96912,1500,2030],"chioula":[42.752655,1.864605,1240,1600],"monts-dolmes":[42.83667,1.74317,1500,2000],"mijanes":[42.72263,2.00944,1530,2000],"camurac":[42.77377,1.921125,1400,1800],"porte":[42.549605,1.79655,1600,2500],"font-romeu":[42.52471,2.02567,1750,2213],"cambre-daze":[42.472775,2.111295,1640,2450],"les-angles":[42.571445,2.051735,1600,2400],"formigueres":[42.623625,2.05115,1700,2350],"pas-de-la-case":[42.54215,1.72508,2050,2640]}

HOSTS = ['api.open-meteo.com', 'previous-runs-api.open-meteo.com']
def http(url, timeout=120, binary=False):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read()
    return b if binary else b.decode('utf-8', 'ignore')

def om(locs, params):
    """locs: [(lat, lon, elev|None)] → liste de réponses Open-Meteo (essaie plusieurs hôtes)."""
    q = {'latitude': ','.join(f'{p[0]:.4f}' for p in locs), 'longitude': ','.join(f'{p[1]:.4f}' for p in locs), **params}
    if locs[0][2] is not None: q['elevation'] = ','.join(str(p[2]) for p in locs)
    last = None
    for host in HOSTS:
        for k in range(4):
            try:
                d = json.loads(http(f'https://{host}/v1/forecast?' + urllib.parse.urlencode(q)))
                d = d if isinstance(d, list) else [d]
                if d and 'error' not in d[0]:
                    time.sleep(6); return d
                last = d[0].get('reason')
            except urllib.error.HTTPError as e:
                try: last = json.loads(e.read().decode()).get('reason', str(e))
                except Exception: last = str(e)
                if e.code == 429 and 'inute' not in last: break   # quota horaire/journalier de cet hôte : hôte suivant
                time.sleep(65 if e.code == 429 else 5); continue    # limite à la minute : on patiente
            except Exception as e:
                last = str(e)
            time.sleep(5 * (k + 1))
    raise RuntimeError('Open-Meteo indisponible : ' + str(last))

r1 = lambda x: round(x or 0, 1)
def episodes(times, sf):
    """Épisodes neigeux : heures enneigées, trous ≤ 6 h fusionnés, total ≥ 0,5 cm."""
    eps = []; cur = None; gap = 0
    for t, v in zip(times, sf):
        if v > 0:
            if cur and gap <= 6: cur['e'] = t; cur['cm'] += v
            else:
                if cur: eps.append(cur)
                cur = {'s': t, 'e': t, 'cm': v}
            gap = 0
        elif cur:
            gap += 1
    if cur: eps.append(cur)
    return [dict(e, cm=round(e['cm'], 1)) for e in eps if e['cm'] >= 0.5]

def point(r, alt):
    H = r['hourly']; T = H['time']; D = r['daily']
    ni = T.index(NOW) if NOW in T else max(i for i, t in enumerate(T) if t <= NOW)
    sf = [x or 0 for x in H['snowfall']]
    past = lambda h: r1(sum(sf[max(0, ni - h + 1):ni + 1]))
    fut = lambda h: r1(sum(sf[ni + 1:ni + 1 + h]))
    fl = [x for x in H['freezing_level_height'][ni:ni + 73] if x is not None]
    eps = episodes(T, sf)
    last = [e for e in eps if e['s'] <= NOW]; nxt = [e for e in eps if e['s'] > NOW]
    # chutes des dernières 72 h par tranches de 6 h : [début, cm, isotherme 0 °C le plus bas pendant la chute]
    # (la page s'en sert pour corriger l'enneigement satellite, aveugle sous les nuages pendant et juste après une chute)
    FLh = H['freezing_level_height']; rec = []
    for i0 in range(max(0, ni - 71), ni + 1, 6):
        hs = [i for i in range(i0, min(i0 + 6, ni + 1)) if sf[i] > 0]
        if hs: rec.append([T[i0], r1(sum(sf[i] for i in hs)) or 0.1, int(round(min((FLh[i] or 0) for i in hs) / 10) * 10)])
    return {'alt': alt, 'elev': r.get('elevation'), 'c24': past(24), 'c72': past(72), 'c7': past(168), 'c14': r1(sum(sf[:ni + 1])),
            'f72': fut(72), 'f7': fut(168), 'sd': round((H['snow_depth'][ni] or 0) * 100),
            'fl': int(round((H['freezing_level_height'][ni] or 0) / 10) * 10), 'flmin72': int(round(min(fl or [0]) / 10) * 10),
            't': r1(H['temperature_2m'][ni]), 'last': last[-1] if last else None, 'next': nxt[0] if nxt else None, 'rec': rec,
            'daily': [r1(x) for x in D['snowfall_sum']], 'tmin': [r1(x) for x in D['temperature_2m_min']], 'tmax': [r1(x) for x in D['temperature_2m_max']]}

def save(name, obj):
    p = os.path.join(DATA, name)
    with open(p + '.tmp', 'w') as f: json.dump(obj, f, separators=(',', ':'), ensure_ascii=False)
    os.replace(p + '.tmp', p); CHANGED.append('data/' + name)

# ---------- secours météo : MET Norway (api.met.no), quand le quota Open-Meteo de l'adresse partagée est épuisé ----------
SYM = [('thunder', 95), ('heavysnow', 75), ('lightsnow', 71), ('snow', 73), ('sleet', 67), ('heavyrain', 65), ('lightrain', 61), ('rain', 63),
       ('fog', 45), ('partlycloudy', 2), ('cloudy', 3), ('fair', 1), ('clearsky', 0)]
def metno(la, lo, alt):
    u = f'https://api.met.no/weatherapi/locationforecast/2.0/complete?lat={la:.4f}&lon={lo:.4f}&altitude={int(alt)}'
    req = urllib.request.Request(u, headers={'User-Agent': 'NeigePyrenees/1.2 (site personnel, bulletin neige Pyrenees)'})
    for k in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as r: return json.loads(r.read().decode())['properties']['timeseries']
        except Exception as e:
            last = e; time.sleep(2 * (k + 1))
    raise RuntimeError('MET Norway indisponible : ' + str(last))
def metno_days(ts, days):
    """Agrège la série MET Norway par jour (heure de Paris) : tn, tx, précipitations, neige, vent, soleil, code temps ; et série horaire de neige."""
    D = {d: {'t': [], 'p': 0.0, 'sf': 0.0, 'w': 0.0, 'sun': 0.0, 'sym': []} for d in days}; hrs = []
    for k, it in enumerate(ts):
        t = datetime.fromisoformat(it['time'].replace('Z', '+00:00')).astimezone(TZ); d = t.strftime('%Y-%m-%d'); x = it['data']; ins = x['instant']['details']
        n1, n6 = x.get('next_1_hours'), x.get('next_6_hours'); blk = n1 or n6; step = 1 if n1 else 6
        T = ins.get('air_temperature'); pr = (blk or {}).get('details', {}).get('precipitation_amount', 0) or 0
        sf = pr * (1.3 if T is not None and T <= -5 else 1.0 if T is not None and T <= 0.3 else 0.5 if T is not None and T <= 1.5 else 0)
        for j in range(step if blk else 0): hrs.append(((t + timedelta(hours=j)).strftime('%Y-%m-%dT%H:00'), sf / step))
        if d not in D: continue
        o = D[d]
        if T is not None: o['t'].append(T)
        if n6 and not n1:
            dd = n6.get('details', {}); o['t'] += [v for v in (dd.get('air_temperature_min'), dd.get('air_temperature_max')) if v is not None]
        o['p'] += pr; o['sf'] += sf; o['w'] = max(o['w'], (ins.get('wind_speed') or 0) * 3.6)
        if blk:
            for j in range(step):
                if 8 <= (t.hour + j) % 24 < 17: o['sun'] += max(0, 1 - (ins.get('cloud_area_fraction') or 0) / 100)
            if 7 <= t.hour <= 17: o['sym'].append(blk.get('summary', {}).get('symbol_code', ''))
    def code(L):
        if not L: return 3
        rank = {}
        for sy in L:
            c = next((c for k, c in SYM if k in sy), 3); rank[c] = rank.get(c, 0) + 1
        wet = [c for c in rank if c >= 45 and rank[c] >= max(1, len(L) // 4)]
        return max(wet) if wet else max(rank, key=rank.get)
    return {d: {'tn': min(o['t']) if o['t'] else None, 'tx': max(o['t']) if o['t'] else None, 'p': o['p'], 'sf': o['sf'], 'w': o['w'], 'sun': min(9.5, o['sun']), 'wc': code(o['sym'])} for d, o in D.items()}, hrs
def meteo_secours(old):
    """Reconstruit meteo.json à partir de l'ancien fichier (passé, neige au sol) et des prévisions MET Norway (7 jours)."""
    td = NOWDT.strftime('%Y-%m-%d'); d0 = NOWDT.date()
    days = [(d0 + timedelta(days=k)).isoformat() for k in range(-14, 7)]; fut = days[14:]
    od = {d: i for i, d in enumerate(old['days'])}
    pts = [(sid, lv, la, lo, alt) for sid, (la, lo, mn, mx) in ST.items() for lv, alt in (('haut', mx), ('bas', mn))]
    with cf.ThreadPoolExecutor(6) as ex: res = list(ex.map(lambda p: metno(p[2], p[3], p[4]), pts))
    out = {}
    for p, ts in zip(pts, res):
        sid, lv, la, lo, alt = p; agg, hrs = metno_days(ts, fut); o = old['stations'].get(sid, {}).get(lv, {})
        pick = lambda key, d, dflt=0: (o.get(key) or [])[od[d]] if d in od and od[d] < len(o.get(key) or []) else dflt
        daily = [r1(agg[d]['sf']) if d in agg and d >= td else r1(pick('daily', d)) for d in days]
        tmin = [r1(agg[d]['tn']) if d in agg and agg[d]['tn'] is not None else r1(pick('tmin', d)) for d in days]
        tmax = [r1(agg[d]['tx']) if d in agg and agg[d]['tx'] is not None else r1(pick('tmax', d)) for d in days]
        tnow = ts[0]['data']['instant']['details'].get('air_temperature', 0); fl = lambda T: int(round(max(0, alt + T / 0.0065) / 10) * 10)
        t72 = [it['data']['instant']['details'].get('air_temperature', tnow) for it in ts[:60]]
        eps = [e for e in episodes([h[0] for h in hrs], [h[1] for h in hrs]) if e['s'] > NOW]
        new = sum(daily[14:15])   # neige tombée ou attendue aujourd'hui : ajoutée au manteau connu
        s = out.setdefault(sid, {'lat': la, 'lon': lo})
        s[lv] = {'alt': alt, 'elev': o.get('elev'), 'c24': r1(daily[14] + daily[13] * .3), 'c72': r1(sum(daily[12:15])), 'c7': r1(sum(daily[8:15])), 'c14': r1(sum(daily[:15])),
                 'f72': r1(sum(daily[15:18])), 'f7': r1(sum(daily[15:])), 'sd': o.get('sd', 0), 'fl': fl(tnow), 'flmin72': fl(min(t72)), 't': r1(tnow),
                 'last': o.get('last'), 'next': eps[0] if eps else None, 'daily': daily, 'tmin': tmin, 'tmax': tmax}
        if lv == 'haut':
            s['wx'] = {'wc': [agg[d]['wc'] for d in fut], 'g': [round(agg[d]['w'] * 2.0) for d in fut], 'w': [round(agg[d]['w']) for d in fut], 'sun': [r1(agg[d]['sun']) for d in fut],
                       'p': [r1(agg[d]['p']) for d in fut], 'tx': [r1(agg[d]['tx']) for d in fut], 'tn': [r1(agg[d]['tn']) for d in fut]}
    return days, out
def grid_shift(old, days):
    """Grille des chutes de l'ancien fichier, recalée sur les nouveaux jours (les jours inconnus valent 0)."""
    g = old.get('grid'); od = {d: i for i, d in enumerate(old.get('days', []))}
    if not g: return None
    n = len(old['days']); v = []
    for c in range(g['nx'] * g['ny']):
        row = g['v'][c * n:(c + 1) * n]; v += [row[od[d]] if d in od and od[d] < len(row) else 0 for d in days]
    return dict(g, v=v)

def do_meteo():
    pts = []
    for sid, (la, lo, mn, mx) in ST.items(): pts += [(sid, 'haut', la, lo, mx), (sid, 'bas', la, lo, mn)]
    P = {'hourly': 'snowfall,snow_depth,freezing_level_height,temperature_2m',
         'daily': 'snowfall_sum,temperature_2m_max,temperature_2m_min,weather_code,wind_speed_10m_max,wind_gusts_10m_max,sunshine_duration,precipitation_sum',
         'past_days': 14, 'forecast_days': 7, 'timezone': 'Europe/Paris'}
    td = NOWDT.strftime('%Y-%m-%d'); old = None
    try: old = json.load(open(os.path.join(DATA, 'meteo.json')))
    except Exception: pass
    try:
        res = []
        for i in range(0, len(pts), 20): res += om([(p[2], p[3], p[4]) for p in pts[i:i + 20]], P)
    except RuntimeError as e:
        if not old: raise
        days, out = meteo_secours(old)   # Open-Meteo refuse : prévisions MET Norway, passé et neige au sol de l'ancien fichier
        save('meteo.json', {'now': NOW, 'updated': STAMP, 'src': 'MET Norway (secours, Open-Meteo indisponible)', 'secours': True, 'days': days, 'today': 14,
                            'stations': out, 'grid': grid_shift(old, days), 'wxStart': td})
        print('météo de secours MET Norway :', e); return out
    days = res[0]['daily']['time']; today = days.index(td)
    out = {}
    for p, r in zip(pts, res):
        s = out.setdefault(p[0], {'lat': p[2], 'lon': p[3]}); s[p[1]] = point(r, p[4])
        if p[1] == 'haut':
            D = r['daily']; sl = slice(today, today + 7)
            s['wx'] = {'wc': D['weather_code'][sl], 'g': [round(x or 0) for x in D['wind_gusts_10m_max'][sl]],
                       'w': [round(x or 0) for x in D['wind_speed_10m_max'][sl]], 'sun': [r1((x or 0) / 3600) for x in D['sunshine_duration'][sl]],
                       'p': [r1(x) for x in D['precipitation_sum'][sl]], 'tx': [r1(x) for x in D['temperature_2m_max'][sl]],
                       'tn': [r1(x) for x in D['temperature_2m_min'][sl]]}
    # carte des chutes : grille de 0,1° ; si le quota tombe en cours de route, on garde l'ancienne grille recalée
    lats = [round(42.35 + 0.1 * j, 2) for j in range(10)]; lons = [round(-0.40 + 0.1 * i, 2) for i in range(31)]
    G = [(la, lo, None) for la in lats for lo in lons]; grid = None
    try:
        gres = []
        for i in range(0, len(G), 62): gres += om(G[i:i + 62], {'daily': 'snowfall_sum', 'past_days': 14, 'forecast_days': 7, 'timezone': 'Europe/Paris'})
        v = []
        for r in gres:
            d = r['daily']['snowfall_sum']; d = (d + [0] * len(days))[:len(days)]
            v += [int(round((x or 0) * 10)) for x in d]
        grid = {'lon0': -0.4, 'lat0': 42.35, 'd': 0.1, 'nx': 31, 'ny': 10, 'v': v}
    except RuntimeError as e:
        grid = grid_shift(old, days) if old else None
        if not grid: raise
        print('grille des chutes non actualisée :', e)
    save('meteo.json', {'now': NOW, 'updated': STAMP, 'src': 'Open-Meteo (modèles Météo-France, DWD et ECMWF)', 'days': days, 'today': today,
                        'stations': out, 'grid': grid, 'wxStart': td})
    return out

def do_routes():
    p = os.path.join(DATA, 'routes.json')
    if not os.path.exists(p): print('routes.json absent, cols non actualisés'); return
    R = json.load(open(p)); out = R['r']; pts = []
    for rid, v in out.items():
        pts += [(rid, 'col', v['c'][v['ci']][1], v['c'][v['ci']][0], v['top']), (rid, 'pied', v['c'][0][1], v['c'][0][0], v['foot'])]
    MM = om([(p[2], p[3], p[4]) for p in pts], {'hourly': 'snowfall,snow_depth,temperature_2m', 'past_days': 2, 'forecast_days': 3, 'timezone': 'Europe/Paris'})
    for p, r in zip(pts, MM):
        H = r['hourly']; t = H['time']; ni = t.index(NOW); sf = [x or 0 for x in H['snowfall']]; tt = [x for x in H['temperature_2m'][ni:ni + 24] if x is not None]
        out[p[0]].setdefault('met', {})[p[1]] = {'sd': r1((H['snow_depth'][ni] or 0) * 100), 'f24': r1(sum(sf[ni - 23:ni + 1])),
                                                 'n24': r1(sum(sf[ni + 1:ni + 25])), 't': H['temperature_2m'][ni], 'tmin24': min(tt or [0])}
    R['updated'] = STAMP; save('routes.json', R)

# ---------- comptage des personnes sur les webcams (YOLO11n) ----------
import subprocess
import numpy as np
# Comptage des personnes visibles sur une image de webcam (YOLO11n, ONNX, CPU).
# Utilisé par update.py ; renvoie None si le modèle ou onnxruntime ne sont pas disponibles.
MODEL_URL = 'https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.onnx'
_S = None
def _session():
    global _S
    if _S is not None: return _S or None
    try:
        try: import onnxruntime as ort
        except ImportError:
            subprocess.run([sys.executable, '-m', 'pip', 'install', '--break-system-packages', '-q', 'onnxruntime'], check=False, capture_output=True)
            import importlib; importlib.invalidate_caches()
            import onnxruntime as ort
        p = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'yolo11n.onnx')
        if not os.path.exists(p) or os.path.getsize(p) < 1e6:
            urllib.request.urlretrieve(MODEL_URL, p)
        o = ort.SessionOptions(); o.intra_op_num_threads = 4
        _S = ort.InferenceSession(p, o, providers=['CPUExecutionProvider'])
    except Exception as e:
        print('comptage indisponible :', e); _S = False
    return _S or None
def _nms(b, s, thr=.5):
    keep = []; idx = s.argsort()[::-1]
    while len(idx):
        i = idx[0]; keep.append(i)
        if len(idx) == 1: break
        xx1 = np.maximum(b[i, 0], b[idx[1:], 0]); yy1 = np.maximum(b[i, 1], b[idx[1:], 1]); xx2 = np.minimum(b[i, 2], b[idx[1:], 2]); yy2 = np.minimum(b[i, 3], b[idx[1:], 3])
        inter = np.clip(xx2 - xx1, 0, None) * np.clip(yy2 - yy1, 0, None)
        a = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1]); iou = inter / (a[i] + a[idx[1:]] - inter + 1e-9)
        idx = idx[1:][iou < thr]
    return keep
def count_people(im, conf=.33):
    """im : image PIL. Renvoie le nombre de personnes détectées (sur la pleine image, jusqu'à 1280 px de large)."""
    s = _session()
    if s is None: return None
    from PIL import Image
    im = im.convert('RGB'); w, h = im.size; sc = min(1.0, 1280 / max(w, h))
    W, H = int(round(w * sc / 32)) * 32 or 32, int(round(h * sc / 32)) * 32 or 32
    x = np.asarray(im.resize((W, H), Image.BILINEAR), dtype=np.float32).transpose(2, 0, 1)[None] / 255.
    out = s.run(None, {s.get_inputs()[0].name: x})[0][0]   # (84, N)
    sc0 = out[4]; m = sc0 > conf
    if not m.any(): return 0
    c = out[:4, m].T; sco = sc0[m]
    b = np.stack([c[:, 0] - c[:, 2] / 2, c[:, 1] - c[:, 3] / 2, c[:, 0] + c[:, 2] / 2, c[:, 1] + c[:, 3] / 2], 1)
    return len(_nms(b, sco))

# ---------- webcams (Pyreneige) ----------
M = {"luz-ardiden":"station-ski/luz-ardiden","cauterets":"station-ski/cauterets-cirque-du-lys","grand-tourmalet":"station-ski/grand-tourmalet","pic-du-midi":"station-ski/grand-tourmalet",
"piau-engaly":"station-ski/piau-engaly","saint-lary":"station-ski/saint-lary","peyragudes":"station-ski/peyragudes","val-louron":"station-ski/val-louron","gavarnie":"station-ski/gavarnie-gedre",
"hautacam":"station-ski/hautacam","val-dazun":"espace-nordique/val-dazun","nistos":"espace-nordique/nistos","superbagneres":"station-ski/luchon-superbagneres","le-mourtis":"station-ski/le-mourtis",
"guzet":"station-ski/guzet","goulier":"station-ski/goulier-neige","beille":"espace-nordique/beille","ax-3-domaines":"station-ski/ax-3-domaines","ascou":"station-ski/ascou-pailheres",
"chioula":"espace-nordique/chioula","monts-dolmes":"station-ski/les-monts-dolmes","mijanes":"station-ski/mijanes-donezan","camurac":"station-ski/camurac","porte":"station-ski/porte-puymorens",
"font-romeu":"station-ski/font-romeu-pyrenees-2000","cambre-daze":"station-ski/cambre-daze","les-angles":"station-ski/les-angles","formigueres":"station-ski/formigueres","pas-de-la-case":"station-ski/grandvalira"}

def boxes(h):
    out = []
    for b in h.split('class="webcam_box"')[1:]:
        t = re.search(r'webcam_tit"><strong>(.*?)</strong>', b); a = re.search(r'webcam_author">(?:<a[^>]*>)?(.*?)<', b)
        im = re.search(r'href="(https://www\.pyreneige\.fr/webcams/[^"]+\.jpg)"', b)
        if im: out.append({'t': html.unescape(t.group(1)).strip() if t else '', 'a': html.unescape(a.group(1)).strip() if a else '', 'u': im.group(1)})
    return out

def do_cams():
    from PIL import Image
    import io
    oldp = os.path.join(DATA, 'cams.json')
    old = json.load(open(oldp))['cams'] if os.path.exists(oldp) else {}
    pages = {}
    def page(slug):
        if slug not in pages:
            try: pages[slug] = http(f'https://www.pyreneige.fr/{slug}/webcams/', 40)
            except Exception: pages[slug] = ''
        return pages[slug]
    with cf.ThreadPoolExecutor(8) as ex: list(ex.map(page, sorted(set(M.values()))))
    res = {}
    for sid, slug in M.items():
        bx = boxes(page(slug))
        if sid == 'pas-de-la-case': bx = [b for b in bx if re.search(r'Pas de la Casa|Envalira|Francia', b['t'])] or bx
        if sid == 'pic-du-midi': bx = [b for b in bx if re.search(r'pic', b['t'], re.I)] or bx[:2]
        if sid == 'grand-tourmalet': bx = [b for b in bx if not re.search(r'pic du midi', b['t'], re.I)] or bx
        res[sid] = bx[:5]
    def dl(j):
        sid, i, b = j; out = os.path.join(CAMS, f'{sid}-{i}.jpg')
        m = re.search(r'_(\d{4})-(\d\d)-(\d\d)-(\d\d)-(\d\d)', b['u'])
        b['ts'] = f'{m.group(1)}-{m.group(2)}-{m.group(3)}T{m.group(4)}:{m.group(5)}' if m else ''
        prev = (old.get(sid) or [])
        prev = prev[i] if i < len(prev) else None
        if prev and prev.get('ts') == b['ts'] and b['ts'] and os.path.exists(out):   # image inchangée
            b.update(f=prev['f'], w=prev['w'], h=prev['h'], p=prev.get('p')); return False
        try:
            im = Image.open(io.BytesIO(http(b['u'], 40, binary=True))).convert('RGB'); w, h = im.size; sc = min(1, 880 / w)
            try: b['p'] = count_people(im)
            except Exception: b['p'] = None
            im = im.resize((round(w * sc), round(h * sc)), Image.LANCZOS); im.save(out, quality=72, optimize=True, progressive=True)
            b.update(f=f'cams/{sid}-{i}.jpg', w=im.size[0], h=im.size[1]); return True
        except Exception:
            if prev and os.path.exists(out): b.update(f=prev['f'], w=prev['w'], h=prev['h'], ts=prev.get('ts', ''))
            else: b['f'] = None
            return False
    jobs = [(sid, i, b) for sid, bx in res.items() for i, b in enumerate(bx)]
    with cf.ThreadPoolExecutor(10) as ex: new = list(ex.map(dl, jobs))
    for (sid, i, b), n in zip(jobs, new):
        if n: CHANGED.append(b['f'])
    cams = {sid: [{k: b[k] for k in ('t', 'a', 'f', 'ts', 'w', 'h', 'p') if k in b and b[k] is not None} for b in bx if b.get('f')] for sid, bx in res.items()}
    for sid in M:                      # page Pyreneige muette : on garde les images précédentes
        if not cams.get(sid) and old.get(sid): cams[sid] = old[sid]
    save('cams.json', {'src': 'Pyreneige.fr (webcams des stations)', 'updated': STAMP, 'cams': cams,
                       'pages': {k: f'https://www.pyreneige.fr/{v}/webcams/' for k, v in M.items()}})
    return sum(new), len(jobs)


# ---------- état d'ouverture officiel (pages station Pyreneige) ----------

# ---------- enneigement observé par satellite (NASA GIBS : MODIS Terra/Aqua, VIIRS SNPP/NOAA-20/NOAA-21) ----------
# Pour chaque jour des 8 derniers jours et chaque satellite : image en fausses couleurs 7-2-1 (neige cyan, nuages blancs,
# végétation verte) + produit NDSI. Un pixel est « neige » si les deux concordent, « sol » s'il est clairement dégagé.
# Composite : l'observation dégagée la plus récente de chaque pixel. Sortie : data/snowobs.png (gris, 1220×360 sur la carte)
# 0 = inconnu, 10+âge = sol, 50+âge = neige (âge en jours avant la date la plus récente), et data/snowobs.json.
SNB = (-0.4, 42.35, 2.65, 43.25); SNW, SNH = 1220, 360
SNS = [('MODIS_Terra', 'MODIS_Terra_CorrectedReflectance_Bands721'), ('MODIS_Aqua', 'MODIS_Aqua_CorrectedReflectance_Bands721'),
       ('VIIRS_NOAA20', 'VIIRS_NOAA20_CorrectedReflectance_BandsM11-I2-I1'), ('VIIRS_NOAA21', 'VIIRS_NOAA21_CorrectedReflectance_BandsM11-I2-I1'),
       ('VIIRS_SNPP', 'VIIRS_SNPP_CorrectedReflectance_BandsM11-I2-I1')]
def do_snow():
    from PIL import Image
    import io
    def gibs(layer, d, png):
        u = ('https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?SERVICE=WMS&REQUEST=GetMap&VERSION=1.1.1&STYLES=&SRS=EPSG:4326'
             f'&LAYERS={layer}&FORMAT=image/{"png" if png else "jpeg"}&BBOX={",".join(map(str, SNB))}&WIDTH={SNW}&HEIGHT={SNH}&TIME={d}')
        try: return Image.open(io.BytesIO(http(u, 90, binary=True)))
        except Exception: return None
    days = [(NOWDT - timedelta(days=k)).strftime('%Y-%m-%d') for k in range(9)]
    jobs = [(d, sen, lay) for d in days for sen, lay in SNS]
    with cf.ThreadPoolExecutor(10) as ex:
        imgs = list(ex.map(lambda j: (gibs(j[2], j[0], False), gibs(j[1] + '_NDSI_Snow_Cover', j[0], True)), jobs))
    st = np.zeros((SNH, SNW), np.uint8); latest = None; used = []
    for k, d in enumerate(days):
        sn = np.zeros((SNH, SNW), bool); gr = np.zeros((SNH, SNW), bool)
        for (dd, sen, lay), (fc, nd) in zip(jobs, imgs):
            if dd != d or fc is None: continue
            a = np.asarray(fc.convert('RGB')).astype(np.int16); R, G, B = a[..., 0], a[..., 1], a[..., 2]
            ndsi = np.asarray(nd.convert('RGBA'))[..., 3] > 0 if nd is not None else np.zeros((SNH, SNW), bool)
            L = (R + G + B) / 3; nodata = (R + G + B) < 12
            cyan = (B > 120) & (G > 120) & (R < 0.72 * np.minimum(G, B))
            veg = (G > R + 12) & (G > B + 12) & (L < 170); rock = (R >= G - 5) & (B < G + 5) & (L < 170) & ~cyan
            s1 = cyan & ndsi & ~nodata; g1 = (veg | rock) & ~nodata
            if s1.any() or g1.mean() > .02: used.append(f'{sen} {d}')
            sn |= s1; gr |= g1
        if (sn | gr).mean() > .02 and latest is None: latest = d
        if latest is None: continue
        age = (datetime.fromisoformat(latest) - datetime.fromisoformat(d)).days
        new = (st == 0) & (sn | gr); st[new & sn] = 50 + age; st[new & ~sn & gr] = 10 + age
    if latest is None: raise RuntimeError('aucune image satellite exploitable')
    p = os.path.join(DATA, 'snowobs.png'); Image.fromarray(st, 'L').save(p, optimize=True); CHANGED.append('data/snowobs.png')
    save('snowobs.json', {'src': 'NASA GIBS (MODIS Terra/Aqua, VIIRS SNPP/NOAA-20/NOAA-21), classification neige/sol', 'updated': STAMP, 'latest': latest,
                          'bbox': SNB, 'w': SNW, 'h': SNH, 'known': round(float((st > 0).mean()), 3), 'passes': len(used)})
    return latest

def do_status():
    def txt(h):
        h = re.sub(r'<script.*?</script>|<style.*?</style>', '', h, flags=re.S)
        return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', h)))
    pages = {}
    def page(slug):
        try: return slug, http(f'https://www.pyreneige.fr/{slug}/', 40)
        except Exception: return slug, ''
    with cf.ThreadPoolExecutor(8) as ex:
        for slug, h in ex.map(page, sorted(set(M.values()))): pages[slug] = txt(h) if h else ''
    out = {}
    n = lambda v: None if v in (None, '-', '') else int(v)
    for sid, slug in M.items():
        if sid == 'pic-du-midi': continue   # page du Grand Tourmalet : pas de bulletin propre
        t = pages.get(slug, '')
        if not t: continue
        m = re.search(r'(Ouverte|Fermée|Partiellement ouverte|Ouvert|Fermé)\s+\w+\s+(\d\d/\d\d/\d{4})\s+Remontées\s+(\d+|-)\s*/\s*(\d+)\s+Pistes\s+(\d+|-)\s*/\s*(\d+)\s+Neige\s+(\d+|-)', t)
        o = re.search(r'OUVERTURE\s+(\d\d/\d\d/\d{4})\s*(Ouverture non confirmée|Ouverture confirmée)?', t)
        f = re.search(r'FERMETURE\s+(\d\d/\d\d/\d{4})', t)
        d = {}
        if m: d.update(st=m.group(1), day=m.group(2), rem=[n(m.group(3)), int(m.group(4))], pis=[n(m.group(5)), int(m.group(6))], sd=n(m.group(7)))
        if o: d.update(open=o.group(1), conf=bool(o.group(2) and 'non' not in o.group(2)))
        if f: d['close'] = f.group(1)
        # fiche officielle : nombre de pistes par couleur, km, remontées
        off = {k: int(v.group(1)) for k, p in (('v', r'Pistes vertes\s*:\s*(\d+)'), ('b', r'Pistes bleues\s*:\s*(\d+)'), ('r', r'Pistes rouges\s*:\s*(\d+)'), ('n', r'Pistes noires\s*:\s*(\d+)'),
               ('km', r'Kilomètres\s*:\s*(\d+)\s*km'), ('pis', r'INFOS STATION\s+Pistes\s*:\s*(\d+)'), ('rem', r'Remontées\s*:\s*(\d+)\s+Prix')) for v in [re.search(p, t)] if v}
        if off: d['off'] = off
        if d: out[sid] = d
    if not out: raise RuntimeError('aucune page station lisible')
    save('status.json', {'src': 'Pyreneige.fr (bulletins des stations)', 'updated': STAMP, 's': out})
    return len(out)

def age_h(stamp):
    try: return (NOWDT.replace(tzinfo=None) - datetime.fromisoformat(stamp)).total_seconds() / 3600
    except Exception: return 99

if __name__ == '__main__':
    # Les modèles météo ne sortent que toutes les 3 à 6 h : on interroge Open-Meteo au plus toutes les 3 h
    # (quota partagé), les webcams à chaque passage.
    FORCE = '--force' in sys.argv
    errs = []; live_p = os.path.join(DATA, 'live.json')
    live = json.load(open(live_p)) if os.path.exists(live_p) else {}
    for name, fn in (('cams', do_cams), ('status', do_status), ('snow', do_snow), ('meteo', do_meteo), ('routes', do_routes)):
        if name not in ('cams', 'status') and not FORCE and age_h(live.get(name, '')) < (2.9 if name == 'snow' else 2.75) and os.path.exists(os.path.join(DATA, ('snowobs' if name == 'snow' else name) + '.json')):
            print(name, 'à jour (', live.get(name), ')'); continue
        try:
            r = fn(); live[name] = STAMP
            if name == 'cams': print(f'webcams : {r[0]} nouvelles images sur {r[1]}')
            else: print(name, 'ok')
        except Exception as e:
            errs.append(f'{name}: {e}'); print('ERREUR', name, e)
    live.update(v=STAMP, errors=errs); save('live.json', live)
    print('FICHIERS:'); print('\n'.join(dict.fromkeys(CHANGED)))
    sys.exit(1 if 'cams' in ' '.join(errs) else 0)
