# Lecture de la neige sur les webcams : modèle CLIP (vision, quantifié) en classement « zéro exemple »
# entre trois familles de descriptions : sol enneigé / sol sans neige / image inexploitable (nuit, brouillard, image cassée, reflet).
# On regarde surtout la moitié basse de l'image (le sol autour de la caméra), pas les sommets lointains.
import os, json, urllib.request, threading
import numpy as np
from PIL import Image
URL = 'https://huggingface.co/Xenova/clip-vit-base-patch32/resolve/main/onnx/vision_model_quantized.onnx'
MEAN = np.array([0.48145466, 0.4578275, 0.40821073], np.float32); STD = np.array([0.26862954, 0.26130258, 0.27577711], np.float32)
_S = None; _T = None; _LOCK = threading.Lock()
def _load():
    with _LOCK: return _load1()
def _load1():
    global _S, _T
    if _S is not None: return _S or None
    try:
        import onnxruntime as ort
        d = os.environ.get('NEIGE_CACHE') or os.path.join(os.path.expanduser('~'), '.cache', 'neige'); os.makedirs(d, exist_ok=True)
        p = os.path.join(d, 'clip_vision_q.onnx')
        if not os.path.exists(p) or os.path.getsize(p) < 5e7:
            t = f'{p}.{os.getpid()}.tmp'; urllib.request.urlretrieve(URL, t); os.replace(t, p)
        o = ort.SessionOptions(); o.intra_op_num_threads = 4
        _S = ort.InferenceSession(p, o)
        t = json.load(open(os.path.join(os.path.dirname(__file__), 'clip_snow.json')))
        _T = (np.array(t['emb'], np.float32), np.array(t['classes']), (np.array(t['probe']['w'], np.float32), np.array(t['probe']['b'], np.float32)))
    except Exception as e:
        print('analyse des webcams indisponible :', e); _S = False
    return _S or None
def _prep(im):
    w, h = im.size; s = 224 / min(w, h); im = im.resize((max(224, round(w * s)), max(224, round(h * s))), Image.BICUBIC)
    w, h = im.size; l = (w - 224) // 2; t = (h - 224) // 2
    return ((np.asarray(im.crop((l, t, l + 224, t + 224)), np.float32) / 255 - MEAN) / STD).transpose(2, 0, 1)
def _soft(z): z = z - z.max(-1, keepdims=True); z = np.exp(z); return z / z.sum(-1, keepdims=True)
def _zero(e):
    """Classement « zéro exemple » : chaque famille de descriptions (neige, sans neige, inexploitable) contre les autres."""
    E, C = _T[0], _T[1]; lg = 100 * e @ E.T
    return _soft(np.stack([np.log(np.exp(lg[..., C == k] - lg.max(-1, keepdims=True)).sum(-1)) for k in ('snow', 'bare', 'bad')], -1))
def _pix(im):
    """Contrôles simples : image figée ou à bandes, nuit."""
    a = np.asarray(im.resize((160, 90)), np.float32) / 255; L = a.mean(-1)
    if np.abs(np.diff(L, axis=0)).mean() < .006 or np.abs(np.diff(L, axis=1)).mean() < .004: return 'figée'
    if np.median(a.max(-1)) < .13: return 'nuit'
    return None
def cam_snow(im):
    """Renvoie (probabilité de neige au sol autour de la caméra 0-1, probabilité d'image inexploitable 0-1), ou None si le modèle manque."""
    s = _load()
    if s is None: return None
    im = im.convert('RGB'); w, h = im.size
    if _pix(im): return 0.5, 1.0
    crops = [im, im.crop((0, int(h * .4), int(w * .62), h)), im.crop((int(w * .38), int(h * .4), w, h)), im.transpose(Image.FLIP_LEFT_RIGHT)]
    e = s.run(None, {'pixel_values': np.stack([_prep(c) for c in crops])})[0]; e = e / np.linalg.norm(e, axis=1, keepdims=True)
    W, b = _T[2]; low = (e[1] + e[2]) / 2
    P = (_soft((np.concatenate([e[0], low]) @ W.T + b) / 2.5) + _soft((np.concatenate([e[3], low]) @ W.T + b) / 2.5)) / 2   # sonde entraînée (image + miroir), adoucie
    Z = _zero(e[0])
    sn = P[0] / max(1e-6, P[0] + P[1]); bad = max(P[2], Z[2] if Z[2] > .6 else 0)
    return round(float(sn), 2), round(float(bad), 2)
