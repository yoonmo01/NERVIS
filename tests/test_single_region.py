"""Synthetic checks for single-region analysis. No supplied data or live API."""
import json
import numpy as np

from test_analysis import PackageCase
from backend.analysis import analyze_region
from backend.ai_facts import summary_facts
from backend.schemas import RegionAnalysisRequest


class SingleRegionTests(PackageCase):
    def test_requested_region_and_range_only(self):
        data = self.load()
        result = analyze_region(data, 13, 51, 100)
        series = result['comparison']
        self.assertEqual([r['label_id'] for r in series['regions']], [13])
        self.assertEqual(series['samples'], list(range(51, 101)))
        self.assertTrue(all(len(row) == 1 for row in series['zscore']))
        np.testing.assert_allclose(series['bold'], data.bold[50:100, [12]])
        self.assertAlmostEqual(result['signal_statistics']['bold']['mean'], data.bold[50:100, 12].mean())
        self.assertIsNone(series['correlation'])
        for rows in result['major_points'].values():
            self.assertTrue(all(51 <= r['sample'] <= 100 for r in rows))
            self.assertTrue(all(abs(a['sample']-b['sample']) >= 10 for i, a in enumerate(rows) for b in rows[i+1:]))

    def test_one_sample_and_summary_boundary(self):
        result = analyze_region(self.load(), 3, 20, 20)
        self.assertEqual(result['signal_statistics']['bold']['std_ddof0'], 0)
        self.assertIsNone(result['signal_statistics']['bold']['rms_adjacent_change'])
        self.assertEqual(result['major_points']['adjacent_change_z'], [])
        summary = summary_facts('analyze_region', result, {'region_id': 3, 'start': 20, 'end': 20}, 'single')
        self.assertIn('single.signal_statistics', summary['facts'])
        outbound = json.dumps(summary)
        for key in ('"comparison"', '"samples"', '"zscore"', '"bold": [', '"mask_path"', '"t1_path"'):
            self.assertNotIn(key, outbound)
        for arguments in ({'region_id': 0}, {'region_id': 21}, {'region_id': 3, 'start': 20, 'end': 1}):
            with self.assertRaises(ValueError):
                RegionAnalysisRequest.model_validate(arguments)
