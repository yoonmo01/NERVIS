"""Explicit, bounded live checks. Requires prior approval; no supplied data access.

python -m scripts.check_baze models
python -m scripts.check_baze smoke --model <approved-model-id>
"""
import argparse
import json

import numpy as np

from backend.ai import AIError, AnalysisAI, Gateway, Settings
from backend.data import Dataset


def synthetic_dataset():
    samples = np.arange(1, 201)
    bold = np.column_stack([np.sin(samples / (i + 2)) for i in range(20)])
    regions = [{"label_id": i, "hemisphere": "Left" if i <= 10 else "Right",
                "contralateral_id": i + 10 if i <= 10 else i - 10,
                "name_ko": f"합성영역{(i - 1) % 10}", "region_name": f"Synthetic_{i}",
                "thickness_mm": 1.0 + i / 10, "volume_mm3": float(i * 100),
                "color_rgb": [i, i, i]} for i in range(1, 21)]
    manifest = {"units": {"signal": "synthetic"}, "normalization": {"ddof": 0},
                "spatial_reference": "synthetic only"}
    return Dataset("synthetic-smoke-only", manifest, regions, bold,
                   (bold - bold.mean(axis=0)) / bold.std(axis=0), samples,
                   np.arange(1, 21), {"slices": []})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["models", "smoke"])
    parser.add_argument("--model")
    args = parser.parse_args()
    if args.action == "smoke" and not args.model:
        parser.error("smoke requires an explicitly approved --model")
    gateway = None
    try:
        if args.action == "models":
            gateway = Gateway(Settings.load(max_requests=1, model="model-list-only"))
            result = gateway.send("models/")
            models = result.get("data")
            if not isinstance(models, list):
                raise AIError("unexpected_model_list_format")
            print(json.dumps({"requests": gateway.used, "models": [
                {key: item[key] for key in ("id", "owned_by", "type") if key in item}
                for item in models if isinstance(item, dict) and item.get("type", "llm") == "llm"]}, ensure_ascii=False))
        else:
            gateway = Gateway(Settings.load(max_requests=2, model=args.model))
            result = AnalysisAI(gateway).run(synthetic_dataset(), "전전두피질의 좌우 영역 1번과 11번을 전체 샘플에서 비교해줘.", {})
            executed = [{"tool": r["tool"], "parameters": r["parameters"]} for r in result["results"]]
            success = result["status"] == "ok" and any(r["tool"] == "compare_regions" and
                        r["parameters"]["region_a"] == 1 and r["parameters"]["region_b"] == 11 for r in executed)
            print(json.dumps({"passed": success, "model": args.model, "requests": gateway.used,
                              "tools": executed, "status": result["status"], "usage": result["usage"],
                              "receipts": gateway.receipts, "warning": result["warning"],
                              "supplied_data_read": False}, ensure_ascii=False))
            return 0 if success else 1
    except (AIError, ValueError, OSError) as error:
        code = error.code if isinstance(error, AIError) else "configuration_invalid"
        print(json.dumps({"passed": False, "error": code, "requests": gateway.used if gateway else 0,
                          "receipts": gateway.receipts if gateway else []}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
