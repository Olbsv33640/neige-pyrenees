# Alerte du soir : résume la journée de ski de demain à partir de data/meteo.json et data/status.json.
# Usage : python3 -I alert.py <dossier du site>   → texte en français, puis une ligne "NOTABLE: oui|non".
import json, os, sys
from datetime import datetime, date, timedelta
try:
    from zoneinfo import ZoneInfo; NOW = datetime.now(ZoneInfo('Europe/Paris'))
except Exception:
    NOW = datetime.utcnow() + timedelta(hours=1)
SITE = sys.argv[1] if len(sys.argv) > 1 else '.'
N = {"luz-ardiden": "Luz Ardiden", "cauterets": "Cauterets", "grand-tourmalet": "Grand Tourmalet", "pic-du-midi": "Pic du Midi", "piau-engaly": "Piau-Engaly", "saint-lary": "Saint-Lary", "peyragudes": "Peyragudes", "val-louron": "Val Louron", "gavarnie": "Gavarnie-Gèdre", "hautacam": "Hautacam", "val-dazun": "Val d'Azun", "nistos": "Nistos", "superbagneres": "Luchon-Superbagnères", "le-mourtis": "Le Mourtis", "guzet": "Guzet", "goulier": "Goulier", "beille": "Beille", "ax-3-domaines": "Ax 3 Domaines", "ascou": "Ascou-Pailhères", "chioula": "Le Chioula", "monts-dolmes": "Les Monts d'Olmes", "mijanes": "Mijanès-Donezan", "camurac": "Camurac", "porte": "Porté-Puymorens", "font-romeu": "Font-Romeu Pyrénées 2000", "cambre-daze": "Cambre d'Aze", "les-angles": "Les Angles", "pas-de-la-case": "Pas de la Case", "formigueres": "Formiguères"}
NORD = {"val-dazun", "nistos", "beille", "chioula"}
def load(n):
    try: return json.load(open(os.path.join(SITE, 'data', n)))
    except Exception: return None
M, S = load('meteo.json'), load('status.json') or {'s': {}}
if not M: print("Données météo indisponibles ce soir."); print("NOTABLE: non"); sys.exit()
tom = (NOW + timedelta(days=1)).date(); tk = tom.isoformat()
pd = lambda s: datetime.strptime(s, '%d/%m/%Y').date()
days = M['days']; di = days.index(tk) if tk in days else -1
wi = (tom - date.fromisoformat(M['wxStart'])).days if M.get('wxStart') else -1
FR_D = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
FR_M = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
dl = f"{FR_D[tom.weekday()]} {tom.day} {FR_M[tom.month - 1]}"
cm = lambda v: f"{round(v)} cm" if v >= 10 else f"{round(v, 1)} cm".replace('.', ',')
rows, opening, preseason = [], [], []
for sid, name in N.items():
    m = M['stations'].get(sid); st = S['s'].get(sid, {})
    if not m: continue
    o = st.get('open'); od = pd(o) if o else None
    live_open = st.get('st', '') in ('Ouverte', 'Partiellement ouverte')
    is_open = live_open or (od is not None and od <= tom and (not st.get('close') or tom <= pd(st['close'])))
    if od == tom: opening.append(f"{name}{'' if st.get('conf') else ' (non confirmée)'}")
    h = m['haut']; sd = h.get('sd') or 0
    fr = (h['daily'][di - 1] if di > 0 else 0) + (h['daily'][di] if di >= 0 else 0)
    ok = 0 <= wi < len(m['wx']['g'])
    g = m['wx']['g'][wi] if ok else None; sun = m['wx']['sun'][wi] if ok else None
    pr = m['wx']['p'][wi] if ok else 0; wc = m['wx']['wc'][wi] if ok else None
    if not is_open:
        if (h.get('f72') or 0) >= 20: preseason.append((h['f72'], name))
        continue
    sc = 50 + (20 if fr >= 10 else 8 if fr >= 3 else 0) + (14 if (sun or 0) >= 7 else -10 if sun is not None and sun < 2 else 0)
    sc -= (18 if pr >= 6 else 0) + (12 if wc in (45, 48) else 0) + (25 if (wc or 0) >= 95 else 0)
    sc -= 35 if (g or 0) >= 80 else 18 if (g or 0) >= 60 else 0
    sc -= 32 if sd < 10 else 10 if sd < 40 else 0
    rows.append(dict(sid=sid, n=name, sc=sc, fr=fr, sd=sd, g=g, sun=sun, pr=pr, wc=wc, nord=sid in NORD))
rows.sort(key=lambda r: -r['sc'])
out, notable = [f"Ski demain, {dl}"], False
if opening: out.append("Ouverture demain : " + ", ".join(opening) + "."); notable = True
alp = [r for r in rows if not r['nord']]
if alp:
    b = alp[0]; v = 'Go' if b['sc'] >= 65 else 'Bof' if b['sc'] >= 42 else 'Reste au chaud'
    det = [f"{cm(b['fr'])} de fraîche" if b['fr'] >= 3 else None, f"{round(b['sun'])} h de soleil" if b['sun'] is not None else None,
           f"rafales {b['g']} km/h au sommet" if b['g'] is not None else None, f"{cm(b['sd'])} au sol"]
    out.append(f"{v} : {b['n']} ({', '.join(x for x in det if x)}).")
    pow_ = [r for r in alp if r['fr'] >= 10 and (r['g'] or 0) < 60]
    blue = [r for r in alp if (r['sun'] or 0) >= 7 and (r['g'] or 0) < 45 and r['sd'] >= 30]
    if pow_: out.append("Poudreuse : " + ", ".join(f"{r['n']} {cm(r['fr'])}" for r in pow_[:4]) + "."); notable = True
    elif blue: out.append("Grand beau, peu de vent : " + ", ".join(r['n'] for r in blue[:4]) + "."); notable = True
    wind = [r['n'] for r in alp[:6] if (r['g'] or 0) >= 60]
    if wind: out.append("Vent fort, remontées d'altitude menacées : " + ", ".join(wind) + ".")
    if b['sc'] >= 65: notable = True
elif not opening:
    nxt = sorted((pd(st['open']), N[sid]) for sid, st in S['s'].items() if st.get('open') and sid in N and pd(st['open']) > tom)
    out.append("Aucune station ouverte demain." + (f" Prochaine ouverture : {nxt[0][1]} le {nxt[0][0].day} {FR_M[nxt[0][0].month - 1]}." if nxt else ""))
if preseason:
    preseason.sort(reverse=True); out.append("Grosse chute annoncée sur 3 jours : " + ", ".join(f"{n} {cm(v)}" for v, n in preseason[:4]) + ".")
    if preseason[0][0] >= 30: notable = True
out.append("Détails, heure de départ et pistes au soleil sur le site Neige Pyrénées.")
print("\n".join(out)); print("NOTABLE: " + ("oui" if notable else "non"))
