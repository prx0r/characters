import sys, json, subprocess, tempfile, os, pickle
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import LeaveOneGroupOut, cross_val_score
sys.path.insert(0, '/home/box/repos/characters/audition')
import librosa

beats = [json.loads(l) for l in open('/home/box/comedy-audio/laugh_training_beats.jsonl')]
audio_dir = '/home/box/comedy-audio/kt-sets'

all_features = []
for b in beats:
    stem = b['stem']
    path = None
    for ext in ['.m4a', '.mp3', '.webm']:
        p = f'{audio_dir}/{stem}{ext}'
        if os.path.exists(p):
            path = p
            break
    if not path:
        continue

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        wav = tmp.name
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', path, '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', wav], check=True)
    y, sr = librosa.load(wav, sr=16000)
    os.unlink(wav)

    total_dur = len(y) / sr
    hop = int(0.01 * sr)
    env = np.array([np.sqrt(np.mean(y[i:i+hop]**2)) for i in range(0, len(y)-hop, hop)])

    start = b['pos'] * total_dur
    end = start + b['dur']
    s_idx = int(start / 0.01)
    e_idx = int(end / 0.01)
    beat_env = env[s_idx:e_idx]

    if len(beat_env) > 0:
        pause_threshold = 0.01
        n_pauses = 0
        in_pause = False
        pause_total = 0.0
        for i, e in enumerate(beat_env):
            if e < pause_threshold and not in_pause:
                in_pause = True
            elif e >= pause_threshold and in_pause:
                in_pause = False
                n_pauses += 1
                pause_total += i * 0.01

        all_features.append({
            'comedian': stem.split('_')[0],
            'stem': stem,
            'pos': b['pos'], 'dur': b['dur'],
            'pause_before': b['pause_before'], 'wps': b['wps'],
            'laugh': b['laugh'],
            'energy_mean': float(np.mean(beat_env)),
            'energy_std': float(np.std(beat_env)),
            'n_pauses': n_pauses,
            'pause_total': pause_total,
        })

    print(f'Processed {stem} ({len(all_features)} features)', flush=True)

n_comics = len(set(f['comedian'] for f in all_features))
print(f'\n{len(all_features)} beats from {n_comics} comedians', flush=True)

X = np.array([[f['pos'], f['dur'], f['pause_before'], f['wps'],
               f['energy_mean'], f['energy_std'], f['n_pauses'], f['pause_total']] for f in all_features])
y = np.array([f['laugh'] for f in all_features])
groups = np.array([f['comedian'] for f in all_features])

logo = LeaveOneGroupOut()
rf = RandomForestClassifier(n_estimators=100, random_state=42)

X_text = X[:, :4]
scores_text = cross_val_score(rf, X_text, y, cv=logo, groups=groups, scoring='roc_auc')
scores_full = cross_val_score(rf, X, y, cv=logo, groups=groups, scoring='roc_auc')

print(f'\nText-only AUC:  {scores_text.mean():.3f} +/- {scores_text.std():.3f}')
print(f'Text+delivery:  {scores_full.mean():.3f} +/- {scores_full.std():.3f}')
print(f'Delta: {scores_full.mean() - scores_text.mean():+.3f}')

comics = sorted(set(groups))
for i, c in enumerate(comics):
    print(f'  {c}: text={scores_text[i]:.3f} full={scores_full[i]:.3f}')

rf.fit(X, y)
pickle.dump({'features': X, 'labels': y, 'groups': groups, 'model': rf,
             'feature_names': ['pos', 'dur', 'pause_before', 'wps', 'energy_mean', 'energy_std', 'n_pauses', 'pause_total']},
            open('/home/box/repos/characters/audition/voicelab/delivery_aware_model.pkl', 'wb'))
print('\nModel saved: delivery_aware_model.pkl')
names = ['pos', 'dur', 'pause', 'wps', 'e_mean', 'e_std', 'n_pause', 'p_total']
imps = [round(f, 3) for f in rf.feature_importances_]
print(f'Importances: {dict(zip(names, imps))}')
