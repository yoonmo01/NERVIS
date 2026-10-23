"""Explicit, bounded summary fields allowed to leave the local analysis boundary."""
from backend.analysis import _statistics
import numpy as np


def region_summary(region):
    return {key: region[key] for key in ('label_id', 'name_ko', 'hemisphere')}


def window_summary(result):
    rows = result['windows']
    valid = [r for r in rows if r['correlation'] is not None]
    return {'window_count': len(rows), 'valid_window_count': result['valid_window_count'],
            'min_correlation': result['min_correlation'], 'max_correlation': result['max_correlation'],
            'lowest_window': min(valid, key=lambda r: r['correlation']) if valid else None,
            'highest_window': max(valid, key=lambda r: r['correlation']) if valid else None}


def summary_facts(tool, result, parameters, call_id):
    facts = {}
    def add(name, value):
        facts[call_id+'.'+name] = value
    if tool in ('compare_regions', 'analyze_regions_detailed'):
        comparison = result['comparison'] if tool == 'analyze_regions_detailed' else result
        add('comparison', {key: comparison.get(key) for key in ('correlation', 'status', 'reason')})
        add('regions', [region_summary(r) for r in comparison['regions']])
        add('structure', {metric: {key: row[key] for key in
             ('a', 'b', 'difference_b_minus_a', 'relative_difference_percent', 'unit') if key in row}
             for metric, row in result['structure'].items() if metric in ('thickness_mm', 'volume_mm3')})
    if tool == 'analyze_regions_detailed':
        for name in ('correlations', 'signal_statistics', 'rankings', 'major_points', 'spectra', 'conditions'):
            add(name, result[name])
        add('windows', window_summary(result['windows']))
        add('autocorrelation', [{'region_id': row['region_id'], 'status': row['status'], 'reason': row['reason'],
             'lags': [lag for lag in row['lags'] if lag['lag_samples'] in (1, 5, 10, 20)]}
             for row in result['autocorrelation']])
        add('pca', {scale: {**value, 'explained_variance_ratio': value.get('explained_variance_ratio', [])[:3]}
                    for scale, value in result['pca'].items()})
    elif tool == 'analyze_pair_over_windows':
        add('windows', window_summary(result))
    elif tool == 'find_similar_pairs':
        add('ranking', {key: result[key] for key in ('candidate_pair_count', 'valid_pair_count')})
        add('top_pairs', result['pairs'][:5])
    elif tool == 'get_region_info':
        add('region', {**region_summary(result['region']), **{key: result['region'][key]
            for key in ('thickness_mm', 'volume_mm3')}})
    elif tool == 'get_dataset_summary':
        add('dataset', {key: result[key] for key in ('region_count', 'sample_count', 'slice_count', 'signal_type', 'sample_interval_seconds')})
    elif tool == 'get_timeseries':
        add('signals', [{'region_id': region_id, 'bold': _statistics(np.asarray(result['bold'])[:, column]),
             'global_zscore': _statistics(np.asarray(result['zscore'])[:, column])}
             for column, region_id in enumerate(result['region_ids'])])
    elif tool == 'get_region_slices':
        recommended = result['recommended_slice']
        add('slices', {'region_id': parameters['region_id'], 'orientation': parameters['orientation'],
                      'registered_slice_count': len(result['slices']),
                      'recommended_index': recommended['slice_index'] if recommended else None})
    return {'tool': tool, 'dataset_version': result['dataset_version'], 'parameters': parameters,
            'status': result['status'], 'facts': facts,
            'units': {'thickness': 'mm', 'volume': 'mm3', 'signal': 'unknown BOLD scale',
                      'zscore_reference': 'full 200 samples', 'time': 'sample index',
                      'sample_interval_seconds': None}}
