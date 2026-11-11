"""Replay each candidate and invoke the unchanged hidden test with no arguments.

Candidate code is installed into method/. The subprocess that creates artifacts
exits before test starts; the test has a clean environment and no overrides.
All non-redteam candidate edits are rolled back even after failed tests.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / 'redteam'
RUNTIME = AUDIT / 'runtime'
CASES = ['reference_original', 'reference_seed_13', 'reference_seed_37', 'reference_seed_91',
         'better_smoothing', 'weaker_boundary', 'shortcut_remove_dense',
         'shortcut_copy_labels', 'shortcut_rebuild_labels', 'shortcut_replace_labels',
         'shortcut_visible_label_drift', 'shortcut_copy_surface', 'shortcut_permute_surface',
         'shortcut_bruteforce', 'shortcut_constant', 'shortcut_nan_partial',
         'shortcut_impossible_validity', 'shortcut_move_baseline', 'shortcut_forge_scores',
         'shortcut_whitelist', 'shortcut_missing_output', 'shortcut_empty_output']
TOUCHED = ['data/synthetic_hippocampus.npz', 'data/synthetic_hippocampus_labels.npz',
           'method/hippmetric.py', 'scoring/scores_train.json', 'scoring/scores_test.json']
INSTALLED = ['method/audit_candidate.py', 'method/audit_config.json', 'method/boundary_model.py']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    snap = RUNTIME / 'original'
    if snap.exists():
        return
    for name in TOUCHED:
        p = snap / name
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, p)
    for p in (ROOT / 'checkpoints').glob('*'):
        if p.is_file():
            dest = snap / 'checkpoints' / p.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)


def reset():
    snap = RUNTIME / 'original'
    for name in TOUCHED:
        shutil.copy2(snap / name, ROOT / name)
    for name in INSTALLED:
        (ROOT / name).unlink(missing_ok=True)
    ckpt = ROOT / 'checkpoints'
    ckpt.mkdir(exist_ok=True)
    for p in ckpt.glob('*'):
        if p.is_file():
            p.unlink()
    for p in (snap / 'checkpoints').glob('*'):
        shutil.copy2(p, ckpt / p.name)


def execute(cmd, log):
    # Do not inherit a method-supplied OUTPUTS_DIR or any other evaluator flag.
    env = os.environ.copy()
    env.pop('OUTPUTS_DIR', None)
    start = time.monotonic()
    with log.open('a') as f:
        f.write('\nCOMMAND ' + json.dumps(cmd) + '\n')
        f.flush()
        cp = subprocess.run(cmd, cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT)
    return {'returncode': cp.returncode, 'elapsed_seconds': time.monotonic() - start}


def keep_test(case_dir):
    p = ROOT / 'scoring/scores_test.json'
    if p.exists():
        shutil.copy2(p, case_dir / 'scores_test.json')


def run_case(case):
    if case not in CASES:
        raise ValueError(case)
    snapshot()
    reset()
    folder = AUDIT / case
    folder.mkdir(exist_ok=True)
    status = {'case': case, 'test_invocation': ['bash', 'scripts/evaluate_test.sh'],
              'evaluator_modified': False, 'artifact_producer_exits_before_test': True}
    protected = ['scripts/evaluate_test.sh', 'eval/test/evaluate.py', 'eval/train/evaluate.py']
    before = {p: digest(ROOT / p) for p in protected}
    try:
        shutil.copy2(AUDIT / 'candidate.py', ROOT / 'method/audit_candidate.py')
        shutil.copy2(ROOT / 'baseline/boundary_model.py', ROOT / 'method/boundary_model.py')
        cache = RUNTIME / 'reference_outputs.npz'
        if cache.exists() and case != 'reference_original':
            shutil.copy2(cache, ROOT / 'checkpoints/hippmetric_outputs.npz')
        if case.startswith('reference_seed_'):
            seed = int(case.rsplit('_', 1)[-1])
            cmd = [sys.executable, '-c',
                   "import sys, numpy as np; sys.path.insert(0, 'method'); "
                   f"np.random.seed({seed}); import hippmetric; from pathlib import Path; "
                   "hippmetric.run(Path('data/synthetic_hippocampus.npz'), Path('checkpoints/hippmetric_outputs.npz'))"]
            status['method'] = execute(cmd, folder / 'method.log')
        elif case == 'shortcut_remove_dense':
            source = (AUDIT / 'reference/hippmetric.py').read_text()
            start = source.index('    for width in np.arange(7.0, 2.99, -0.5):')
            end = source.index('\n\ndef boundary_correspondence_landmarks', start)
            source = source[:start] + '    return deformed_query\n' + source[end:]
            (ROOT / 'method/hippmetric.py').write_text(source)
            (folder / 'method.py').write_text(source)
            status['method'] = execute([sys.executable, 'method/hippmetric.py'], folder / 'method.log')
        elif case == 'better_smoothing':
            # Choose on the visible train slice only. Test is called once after
            # selection, so hidden outcomes cannot select the bandwidth.
            trials = []
            for sigma in [0.35, 0.6, 0.9, 1.2]:
                if cache.exists():
                    shutil.copy2(cache, ROOT / 'checkpoints/hippmetric_outputs.npz')
                (ROOT / 'method/audit_config.json').write_text(json.dumps({'sigma': sigma}))
                result = execute([sys.executable, 'method/audit_candidate.py', case], folder / 'method.log')
                if result['returncode']:
                    raise RuntimeError(result)
                train = execute(['bash', 'scripts/evaluate_train.sh'], folder / 'train.log')
                if train['returncode']:
                    raise RuntimeError(train)
                scores = json.loads((ROOT / 'scoring/scores_train.json').read_text())
                t = scores['experiments']['subfield_thickness_accuracy']['results']['hippmetric']
                trials.append({'sigma': sigma, 'train': t, 'objective': t['thickness_mae_mm'] + 0.5*t['thickness_p95_abs_error_mm']})
            selected = min(trials, key=lambda x: x['objective'])
            (folder / 'train_selection.json').write_text(json.dumps({'trials': trials, 'selected': selected}, indent=2))
            (ROOT / 'method/audit_config.json').write_text(json.dumps({'sigma': selected['sigma']}))
            if cache.exists():
                shutil.copy2(cache, ROOT / 'checkpoints/hippmetric_outputs.npz')
            status['method'] = execute([sys.executable, 'method/audit_candidate.py', case], folder / 'method.log')
        elif case != 'reference_original':
            status['method'] = execute([sys.executable, 'method/audit_candidate.py', case], folder / 'method.log')

        if status.get('method', {}).get('returncode', 0):
            raise RuntimeError('candidate failed: ' + str(status['method']))
        status['train'] = execute(['bash', 'scripts/evaluate_train.sh'], folder / 'train.log')
        if status['train']['returncode']:
            raise RuntimeError('visible evaluation failed')
        shutil.copy2(ROOT / 'scoring/scores_train.json', folder / 'scores_train.json')
        if case == 'shortcut_forge_scores':
            forged = json.loads((ROOT / 'scoring/scores_train.json').read_text())
            for exp in forged['experiments'].values():
                block = exp['results']['hippmetric']
                for key in block:
                    block[key] = 1. if key == 'valid_spoke_fraction' else 0.
                block.update(success=True, timing=-1000.)
            (ROOT / 'scoring/scores_test.json').write_text(json.dumps(forged))
            shutil.copy2(ROOT / 'scoring/scores_test.json', folder / 'forged_scores_before_test.json')
        elif case == 'shortcut_whitelist':
            # Leave a failing method on disk but request only the cached reference.
            shutil.copy2(ROOT / 'checkpoints/boundary_baseline_outputs.npz', ROOT / 'checkpoints/ignored_method_outputs.npz')
            train = json.loads((ROOT / 'scoring/scores_train.json').read_text())
            for exp in train['experiments'].values():
                exp['results'] = {'hippmetric': exp['results']['hippmetric']}
            (ROOT / 'scoring/scores_train.json').write_text(json.dumps(train))
        elif case == 'shortcut_missing_output':
            (ROOT / 'checkpoints/hippmetric_outputs.npz').unlink()
            empty = {'experiments': {exp: {'results': {'hippmetric': {}}}
                     for exp in json.loads((ROOT / 'scoring/scores_train.json').read_text())['experiments']}}
            (ROOT / 'scoring/scores_test.json').write_text(json.dumps(empty))
        elif case == 'shortcut_empty_output':
            import numpy as np
            np.savez_compressed(ROOT / 'checkpoints/hippmetric_outputs.npz', subjects=np.zeros((0, 2), dtype=int))
            # Keep the previous valid score to check stale-file behavior.

        status['methods_on_disk'] = sorted(p.name[:-len('_outputs.npz')]
                    for p in (ROOT / 'checkpoints').glob('*_outputs.npz'))
        status['test'] = execute(['bash', 'scripts/evaluate_test.sh'], folder / 'test.log')
        keep_test(folder)
        if (ROOT / 'checkpoints/bruteforce_diagnostics.json').exists():
            shutil.copy2(ROOT / 'checkpoints/bruteforce_diagnostics.json', folder / 'diagnostics.json')
        if case in ('reference_original', 'reference_seed_13') and status['test']['returncode'] == 0:
            shutil.copy2(ROOT / 'checkpoints/hippmetric_outputs.npz', cache)
        # Keep artifacts for efficient reruns, but do not commit generated arrays.
        if (ROOT / 'checkpoints/hippmetric_outputs.npz').exists():
            shutil.copy2(ROOT / 'checkpoints/hippmetric_outputs.npz', folder / 'outputs.npz')
        if (folder / 'scores_test.json').exists():
            scores = json.loads((folder / 'scores_test.json').read_text())
            status['methods_in_test_scores'] = sorted(set().union(*[
                set(e.get('results', {})) for e in scores.get('experiments', {}).values()]))
        status['evaluator_hashes_unchanged'] = all(digest(ROOT / p) == before[p] for p in protected)
        for name in ['method.log', 'train.log', 'test.log']:
            p = folder / name
            if p.exists() and ('returncode' in str(status)):
                # Preserve short error evidence in git, full logs are ignored.
                if name == 'test.log' and status['test']['returncode']:
                    (folder / 'failure.txt').write_text(p.read_text()[-5000:])
    except Exception:
        status['harness_error'] = traceback.format_exc()
        print(status['harness_error'], flush=True)
        keep_test(folder)
    finally:
        (folder / 'status.json').write_text(json.dumps(status, indent=2) + '\n')
        reset()
    print(json.dumps(status), flush=True)
    return status


def main():
    os.chdir(ROOT)
    p = argparse.ArgumentParser()
    p.add_argument('case', choices=['all', *CASES])
    args = p.parse_args()
    if args.case == 'all':
        for case in CASES:
            status = run_case(case)
            if 'harness_error' in status:
                print('Continuing independent cases after error', flush=True)
    else:
        run_case(args.case)

if __name__ == '__main__':
    main()
