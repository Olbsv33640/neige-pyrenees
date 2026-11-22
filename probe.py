import json, urllib.request, gzip, io, csv
def get(u, n=None):
    r = urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'NeigePyrenees-probe'}), timeout=120); b = r.read(); return b
for d in ['archive-reseau-nivo-meteorologique', 'donnees-de-modele-de-simulation-nivologique']:
    j = json.loads(get(f'https://www.data.gouv.fr/api/1/datasets/{d}/'))
    print('==', d)
    for r in j['resources']: print(' ', r['title'][:70], '|', r['url'], '|', (r.get('last_modified') or '')[:16], r.get('filesize'))
b = get('https://object.files.data.gouv.fr/meteofrance/data/synchro_ftp/OBS/NIVOSE/nivo_2026.csv.gz'); t = gzip.decompress(b).decode('latin-1').splitlines()
print('== nivo_2026 lines', len(t)); print(t[0][:600])
pyr = {'07952','07953','07964','07959','07969','07972','07980','07981','07957','07955','07970'}
for l in t[-400:]:
    if l.split(';')[0] in pyr: print(l[:400])
