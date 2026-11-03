"""Video -> landmark sequence using MediaPipe Tasks (HandLandmarker + PoseLandmarker).

Model files are NOT bundled. Download them from Google's MediaPipe model page
(hand_landmarker.task and pose_landmarker_lite.task) and pass their paths, or
set ISL_NOVA_HAND_MODEL / ISL_NOVA_POSE_MODEL.

Frames are passed to MediaPipe unmirrored, so handedness labels follow the
same convention as the browser extractor (contract isl-nova-fc-1.0.0).
"""

from __future__ import annotations

import os
from pathlib import Path

HAND_MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/"
                  "float16/1/hand_landmarker.task")
POSE_MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/"
                  "float16/1/pose_landmarker_lite.task")


class ExtractorUnavailable(RuntimeError):
    pass


def default_model_paths() -> tuple[Path | None, Path | None]:
    h = os.environ.get("ISL_NOVA_HAND_MODEL")
    p = os.environ.get("ISL_NOVA_POSE_MODEL")
    return (Path(h) if h else None, Path(p) if p else None)


class LandmarkExtractor:
    """VIDEO-mode landmarkers reused across videos.

    MediaPipe requires strictly increasing timestamps for the lifetime of a
    VIDEO-mode task, so a running clock is kept across videos (each video
    starts one second after the previous one ended).
    """

    def __init__(self, hand_model: Path | None = None, pose_model: Path | None = None, max_side: int = 960):
        hd, pd = default_model_paths()
        hand_model, pose_model = hand_model or hd, pose_model or pd
        if not hand_model or not Path(hand_model).exists():
            raise ExtractorUnavailable("hand_landmarker.task not found (set ISL_NOVA_HAND_MODEL)")
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions
        from mediapipe.tasks.python import vision as v

        self.mp = mp
        self.max_side = max_side
        self._clock_ms = 0
        self.hands = v.HandLandmarker.create_from_options(v.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(hand_model)),
            running_mode=v.RunningMode.VIDEO, num_hands=2,
            min_hand_detection_confidence=0.5, min_tracking_confidence=0.5))
        self.pose = None
        if pose_model and Path(pose_model).exists():
            self.pose = v.PoseLandmarker.create_from_options(v.PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(pose_model)),
                running_mode=v.RunningMode.VIDEO, num_poses=1))

    def close(self):
        self.hands.close()
        if self.pose:
            self.pose.close()

    def video(self, path: Path, max_frames: int = 300) -> tuple[list[dict], float, dict]:
        import cv2

        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError(f"cannot decode video {path}")
        fps = cap.get(cv2.CAP_PROP_FPS)
        fps = fps if fps and 1 <= fps <= 240 else 30.0
        w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        frames: list[dict] = []
        start = self._clock_ms + 1000
        i = 0
        while i < max_frames:
            ok, bgr = cap.read()
            if not ok:
                break
            s = self.max_side / max(bgr.shape[:2])
            if s < 1:  # landmarks are normalised, so downscaling keeps coordinates comparable
                bgr = cv2.resize(bgr, (round(bgr.shape[1] * s), round(bgr.shape[0] * s)), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            img = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)
            ts = start + int(i * 1000 / fps)
            hr = self.hands.detect_for_video(img, ts)
            fr: dict = {"left": None, "right": None, "pose": None}
            for lms, hd in zip(hr.hand_landmarks, hr.handedness, strict=False):
                side = hd[0].category_name.lower()
                if side in ("left", "right") and fr[side] is None:
                    fr[side] = [[p.x, p.y, p.z] for p in lms]
            if self.pose is not None:
                pr = self.pose.detect_for_video(img, ts)
                if pr.pose_landmarks:
                    fr["pose"] = [[p.x, p.y, p.z, getattr(p, "visibility", 1.0) or 0.0] for p in pr.pose_landmarks[0]]
            frames.append(fr)
            self._clock_ms = ts
            i += 1
        cap.release()
        if not frames:
            raise ValueError(f"no decodable frames in {path}")
        meta = {"fps": fps, "width": w, "height": h, "frames": len(frames)}
        return frames, (w / h if h else 1.0), meta
