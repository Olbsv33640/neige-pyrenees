# Comptage des personnes visibles sur une image de webcam (YOLO11n, ONNX, CPU).
# Utilisé par update.py ; renvoie None si le modèle ou onnxruntime ne sont pas disponibles.
import os, sys, subprocess, urllib.request
import numpy as np
MODEL_URL = 'https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.onnx'
_S = None
def _session():
    global _S
    if _S is not None: return _S or None
    try:
        try: import onnxruntime as ort
        except ImportError:
            subprocess.run([sys.executable, '-m', 'pip', 'install', '--break-system-packages', '-q', 'onnxruntime'], check=False, capture_output=True)
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
if __name__ == '__main__':
    from PIL import Image
    for f in sys.argv[1:]: print(f, count_people(Image.open(f)))
