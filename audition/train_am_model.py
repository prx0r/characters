import json, subprocess, tempfile, os, pickle, gc
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold, cross_val_score

specials = [
    ('chris-rock', 'bigger-blacker', '/home/box/comedy-audio/am_events/chris-rock-bigger-blacker-1999-full.json', '/home/box/comedy-audio/chris-rock/chris-rock-bigger-blacker-1999-full.m4a'),
    ('chris-rock', 'bring-pain', '/home/box/comedy-audio/am_events/chris-rock-bring-pain.json', '/home/box/comedy-audio/chris-rock/chris-rock-bring-pain.m4a'),
    ('dave-chappelle', 'equanimity', '/home/box/comedy-audio/am_events/dave-chappelle-equanimity-2017-full.json', '/home/box/comedy-audio/dave-chappelle/dave-chappelle-equanimity-2017-full.m4a'),
    ('george-carlin', 'bad-for-ya', '/home/box/comedy-audio/am_events/george-carlin-its-bad-for-ya.json', '/home/box/comedy-audio/george-carlin/george-carlin-its-bad-for-ya.m4a'),
    ('george-carlin', 'all-diseased', '/home/box/comedy-audio/am_events/george-carlin-you-are-all-diseased.json', '/home/box/comedy-audio/george-carlin/george-carlin-you-are-all-diseased.m4a'),
]

WINDOW = 5.0
STEP = 2.0

import librosa

all_features = []

for comedian, special, events_path, audio_path in specials:
    if not os.path.exists(audio_path) or not os.path.exists(events_path):
        print(f'SKIP {special}', flush=True)
        continue

    events = json.loads(open(events_path).read())
    print(f'\n{comedian} - {special}: {len(events)} events', flush=True)

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        wav = tmp.name
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', audio_path,
                    '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', wav], check=True)
    y, sr = librosa.load(wav, sr=16000)
    os.unlink(wav)

    total_dur = len(y) / sr
    hop = int(0.01 * sr)
    env = np.array([np.sqrt(np.mean(y[i:i+hop]**2)) for i in range(0, len(y)-hop, hop)])
    del y
    gc.collect()

    laugh_mask = np.zeros(len(env), dtype=bool)
    for start, end, intensity in events:
        s_idx = int(start / 0.01)
        e_idx = int(end / 0.01)
        laugh_mask[s_idx:min(e_idx, len(laugh_mask))] = True

    for w_start in np.arange(0, total_dur - WINDOW, STEP):
        s_idx = int(w_start / 0.01)
        e_idx = int((w_start + WINDOW) / 0.01)

        if laugh_mask[s_idx:e_idx].any():
            continue

        next_s = e_idx
        next_e = int((w_start + WINDOW + 2.0) / 0.01)
        has_laugh = laugh_mask[next_s:min(next_e, len(laugh_mask))].any()

        window_env = env[s_idx:e_idx]
        if len(window_env) == 0:
            continue

        pause_threshold = 0.01
        n_pauses = 0
        in_pause = False
        pause_total = 0.0
        for e in window_env:
            if e < pause_threshold and not in_pause:
                in_pause = True
            elif e >= pause_threshold and in_pause:
                in_pause = False
                n_pauses += 1
                pause_total += 0.01

        all_features.append({
            'comedian': comedian,
            'special': special,
            'pos': float(w_start / total_dur),
            'energy_mean': float(np.mean(window_env)),
            'energy_std': float(np.std(window_env)),
            'energy_max': float(np.max(window_env)),
            'energy_min': float(np.min(window_env)),
            'n_pauses': n_pauses,
            'pause_total': pause_total,
            'laugh': int(has_laugh),
        })

    n_laugh = sum(f['laugh'] for f in all_features if f['special'] == special)
    n_total = sum(1 for f in all_features if f['special'] == special)
    print(f'  Windows: {n_total}, laughs: {n_laugh} ({n_laugh/max(n_total,1)*100:.0f}%)', flush=True)

    del env, laugh_mask
    gc.collect()

# Summary
n_laugh = sum(f['laugh'] for f in all_features)
print(f'\nTotal: {len(all_features)} windows, {n_laugh} laughs ({n_laugh/len(all_features)*100:.0f}%)', flush=True)

X = np.array([[f['pos'], f['energy_mean'], f['energy_std'], f['energy_max'], f['energy_min'],
               f['n_pauses'], f['pause_total']] for f in all_features])
y = np.array([f['laugh'] for f in all_features])
groups = np.array([f['comedian'] for f in all_features])

gkf = GroupKFold(n_splits=min(5, len(set(groups))))
rf = RandomForestClassifier(n_estimators=100, random_state=42)
scores = cross_val_score(rf, X, y, cv=gkf, groups=groups, scoring='roc_auc')

print(f'\nCross-comedian AUC: {scores.mean():.3f} +/- {scores.std():.3f}', flush=True)
print(f'Per-fold: {[round(s, 3) for s in scores]}', flush=True)

rf.fit(X, y)
names = ['pos', 'e_mean', 'e_std', 'e_max', 'e_min', 'n_pause', 'p_total']
imps = [round(f, 3) for f in rf.feature_importances_]
print(f'Importances: {dict(zip(names, imps))}', flush=True)

pickle.dump({'features': X, 'labels': y, 'groups': groups, 'model': rf, 'meta': all_features},
            open('/home/box/repos/characters/audition/voicelab/am_delivery_model.pkl', 'wb'))
print('Model saved', flush=True)
