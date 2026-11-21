# Neige Pyrénées

Bulletin interactif en 3D de l'enneigement des stations de ski des Pyrénées d'Occitanie et de Pas de la Case :
webcams, neige observée par satellite, prévisions, ouvertures, routes d'accès.

Le site est publié par GitHub Pages. Une fois le Worker Cloudflare configuré, chaque ouverture lui demande une
actualisation; le Worker déclenche le workflow GitHub Actions sans exposer de jeton dans le navigateur. Les
demandes sont regroupées pendant dix minutes. Le workflow horaire reste actif en secours.

Le Worker est hébergé gratuitement sur Cloudflare Workers. Il est limité à l'origine GitHub Pages de ce site et
utilise un secret `GITHUB_TOKEN` à accès fin, autorisé uniquement sur ce dépôt avec la permission **Actions: read and write**.
L'URL du Worker est définie dans `refresh-config.js`.

Pour forcer une mise à jour sans ouvrir le site : onglet **Actions** → **Actualisation** → **Run workflow**.

Sources : Pyreneige (webcams, état des stations), Open-Meteo et MET Norway (météo), NASA GIBS (neige satellite),
IGN (orthophotos, relief), Copernicus Sentinel-2, OpenStreetMap (pistes, remontées, routes).
