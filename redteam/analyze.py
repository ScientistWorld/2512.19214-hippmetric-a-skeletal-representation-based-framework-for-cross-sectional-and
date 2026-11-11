"""Summarize saved hidden scores; no method execution or array computation.

Use |coefficient|, metric direction, experiment weight, and population SD
across the named successful audit attempts. The future ranking population is
unknown; dominance statements do not depend on this illustrative population.
"""
from pathlib import Path
import json
import math
import statistics

HERE = Path(__file__).resolve().parent
REF_CASE = 'reference_seed_13'

def load_results(case):
    s = json.loads((HERE / case / 'scores_test.json').read_text())
    return {exp: entry['results'].get('hippmetric', {}) for exp, entry in s['experiments'].items()}


def main():
    coeff = json.loads((HERE / 'reference/rank_coefficients.json').read_text())['experiments']
    cases = sorted(p.parent.name for p in HERE.glob('*/status.json'))
    status = {c: json.loads((HERE/c/'status.json').read_text()) for c in cases}
    # Reference reruns are controls, not separate optimization attempts.
    population = [c for c in cases if status[c].get('test', {}).get('returncode') == 0
                  and (not c.startswith('reference_') or c == REF_CASE)]
    scores = {c: load_results(c) for c in cases}
    ref = scores[REF_CASE]
    deviations = {}
    for exp, ed in coeff.items():
        deviations[exp] = {}
        for met, md in ed['metrics'].items():
            values = [scores[c][exp].get(met) for c in population]
            values = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
            deviations[exp][met] = statistics.pstdev(values) if len(values) > 1 else 0.
    rows = {}
    for case in cases:
        delta = 0.
        contributions, missing, nonfinite = {}, [], []
        better = worse = 0
        for exp, ed in coeff.items():
            contributions[exp] = 0.
            for met, md in ed['metrics'].items():
                if not md['coefficient']:
                    continue
                val = scores[case][exp].get(met)
                key = exp + '/' + met
                if val is None:
                    missing.append(key)
                    continue
                if not math.isfinite(val):
                    nonfinite.append(key)
                    continue
                improvement = (val - ref[exp][met]) * (1 if md['higher_is_better'] else -1)
                better += improvement > 1e-14
                worse += improvement < -1e-14
                sd = deviations[exp][met]
                if sd:
                    contribution = ed['weight'] * abs(md['coefficient']) * improvement / sd
                    contributions[exp] += contribution
                    delta += contribution
        rows[case] = {'test_returncode': status[case]['test']['returncode'],
                      'normalized_delta_from_reference': delta,
                      'experiment_contributions': contributions,
                      'missing_scored_values': missing, 'nonfinite_scored_values': nonfinite,
                      'metrics_improved': better, 'metrics_worsened': worse,
                      'rank_status': ('failed test: no valid rank' if status[case]['test']['returncode'] else
                                      'conditional: nonfinite handling not specified' if nonfinite else
                                      'ranked with finite metrics')}
    summary = {'reference': REF_CASE, 'normalization_population': population,
               'normalization': 'population standard deviation; zero-variance metrics contribute zero',
               'coefficient_sign': 'ignored; only magnitude counts',
               'nonfinite_policy': 'not specified by gym prompt; conditional diagnostic treats nonfinite as skipped',
               'metric_standard_deviations': deviations, 'attempts': rows}
    (HERE / 'rank_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    for case, row in rows.items():
        print(f"{case:34s} {row['normalized_delta_from_reference']:+.6f}  {row['rank_status']}")
    seeds = ['reference_seed_13', 'reference_seed_37', 'reference_seed_91']
    spreads = {exp: {met: max(scores[c][exp][met] for c in seeds) - min(scores[c][exp][met] for c in seeds)
                     for met, md in ed['metrics'].items() if md['coefficient'] != 0}
               for exp, ed in coeff.items()}
    (HERE / 'seed_spread.json').write_text(json.dumps({'seeds': [13,37,91], 'dataset_seed': 13,
        'protocol': 'fixed benchmark; set NumPy method seed and rerun full method',
        'spread_by_metric': spreads,
        'rank_delta_spread': max(rows[c]['normalized_delta_from_reference'] for c in seeds) - min(rows[c]['normalized_delta_from_reference'] for c in seeds)}, indent=2) + '\n')

if __name__ == '__main__':
    main()
