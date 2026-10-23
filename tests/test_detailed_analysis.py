"""Synthetic numerical oracles for the compound analysis; no supplied files."""
from dataclasses import replace
import json
import numpy as np

from test_analysis import PackageCase


class DetailedTests(PackageCase):
    def test_known_wave_pca_and_range_are_calculated_without_mutation(self):
        from backend.analysis import analyze_regions_detailed
        data = self.load()
        wave = np.sin(2*np.pi*.05*np.arange(200))
        bold = wave[:, None] * np.arange(1, 21)[None, :]
        data = replace(data, bold=bold, zscore=bold / bold.std(axis=0))
        before = data.bold.copy()
        result = analyze_regions_detailed(data, 1, 11, 51, 150, window=40, step=5)
        self.assertEqual(result['parameters']['start_sample'], 51)
        self.assertEqual(len(result['windows']['windows']), 13)
        self.assertAlmostEqual(result['correlations']['pearson']['correlation'], 1)
        self.assertAlmostEqual(result['spectra'][0]['hann_peak_cycles_per_sample'], .05)
        self.assertAlmostEqual(result['pca']['within_range_zscore']['explained_variance_ratio'][0], 1)
        self.assertEqual(len(result['pca']['within_range_zscore']['components']), 1)
        self.assertAlmostEqual(result['signal_statistics'][0]['bold']['std_ddof0'], np.std(wave[50:150]))
        self.assertTrue(all(51 <= row['sample'] <= 150 for row in result['major_points']['selected_rms_z']))
        np.testing.assert_array_equal(data.bold, before)
        json.dumps(result, allow_nan=False)

    def test_constant_and_short_ranges_keep_available_metrics_without_fake_values(self):
        from backend.analysis import analyze_regions_detailed
        data = self.load()
        constant = replace(data, bold=np.full((200, 20), .1), zscore=np.zeros((200, 20)))
        result = analyze_regions_detailed(constant, 1, 11, 51, 100)
        self.assertEqual(result['correlations']['pearson']['status'], 'unavailable')
        self.assertEqual(result['pca']['raw_centered']['status'], 'unavailable')
        self.assertEqual(result['pca']['within_range_zscore']['status'], 'unavailable')
        self.assertEqual(result['spectra'][0]['status'], 'unavailable')
        self.assertEqual(result['signal_statistics'][0]['bold']['std_ddof0'], 0)
        short = analyze_regions_detailed(data, 1, 11, 51, 53)
        self.assertEqual(short['spectra'][0]['reason'], 'fewer_than_8_samples')
        self.assertEqual(short['autocorrelation'][0]['lags'], [])
        self.assertEqual(short['autocorrelation'][0]['reason'], 'fewer_than_4_samples')
        self.assertEqual(short['parameters']['window'], 3)
        json.dumps(short, allow_nan=False)
        for kwargs in ({'end': 2}, {'window': 201}, {'step': 0}, {'start': 51, 'end': 53, 'step': 4}, {'method': 'bad'}):
            with self.assertRaises(ValueError):
                analyze_regions_detailed(data, 1, 11, **kwargs)
