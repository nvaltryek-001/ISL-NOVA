import os
from pathlib import Path

import pytest
from isl_nova_ml.data import leakage_report
from isl_nova_ml.extract import ExtractorUnavailable, LandmarkExtractor
from isl_nova_ml.include_import import plan

REPO = Path(__file__).resolve().parents[2]
VOCAB = REPO / "dataset" / "vocabulary" / "signs_master.csv"


def test_include_plan_maps_only_vocabulary_classes(tmp_path):
    items = plan(tmp_path, VOCAB)
    sign_ids = {i["sign_id"] for i in items}
    assert len(sign_ids) == 200, "every slot must map to INCLUDE videos"
    assert {i["split"] for i in items} == {"train", "val", "test"}
    assert all(not i["video"].exists() for i in items)  # dataset not present in the repo
    assert len({i["recording_id"] for i in items}) == len(items)


def test_unknown_signer_ids_are_not_treated_as_leakage():
    es = [{"recording_id": f"r{i}", "signer_id": "unknown:include", "session_id": "unknown:include",
           "split": s} for i, s in enumerate(["train", "val", "test"])]
    rep = leakage_report(es)
    assert rep["has_leakage"] is False and rep["signer_ids_unknown"] == 3


def test_extractor_requires_model_files(tmp_path):
    with pytest.raises(ExtractorUnavailable):
        LandmarkExtractor(tmp_path / "missing.task")


@pytest.mark.skipif(not os.environ.get("ISL_NOVA_HAND_MODEL"), reason="MediaPipe hand_landmarker.task not available")
def test_extractor_runs_on_a_video(tmp_path):  # pragma: no cover - needs model + video
    import cv2
    import numpy as np

    p = tmp_path / "blank.mp4"
    vw = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"mp4v"), 30, (64, 48))
    for _ in range(10):
        vw.write(np.zeros((48, 64, 3), np.uint8))
    vw.release()
    ex = LandmarkExtractor()
    frames, aspect, meta = ex.video(p)
    ex.close()
    assert meta["frames"] == 10 and all(f["left"] is None and f["right"] is None for f in frames)
