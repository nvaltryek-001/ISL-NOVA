"""Video -> landmark sequence using MediaPipe Tasks (HandLandmarker + PoseLandmarker).

Model files are NOT bundled. Download them from Google's MediaPipe model page
(hand_landmarker.task, pose_landmarker_lite.task and, for contract 2.0.0,
face_landmarker.task) and pass their paths, or set ISL_NOVA_HAND_MODEL /
ISL_NOVA_POSE_MODEL / ISL_NOVA_FACE_MODEL. With a face model each frame also
carries ``face``: the 22 FaceLandmarker points in ``contract.FACE_KEEP``.

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
FACE_MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/"
                  "float16/1/face_landmarker.task")


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

    def __init__(self, hand_model: Path | None = None, pose_model: Path | None = None, max_side: int = 960,
                 face_model: Path | None = None):
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
        face_model = face_model or (Path(os.environ["ISL_NOVA_FACE_MODEL"]) if os.environ.get("ISL_NOVA_FACE_MODEL") else None)
        self.face = None
        if face_model and Path(face_model).exists():  # non-manual features (contract 2.0.0)
            # IMAGE mode on a head crop: in full-body recordings the face is too small for the
            # short-range face detector, so the crop (from the pose landmarks) is enlarged first.
            self.face = v.FaceLandmarker.create_from_options(v.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(face_model)),
                running_mode=v.RunningMode.IMAGE, num_faces=1))

    def close(self):
        self.hands.close()
        if self.pose:
            self.pose.close()
        if self.face:
            self.face.close()

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
            full = bgr
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
            if self.face is not None:
                fr["face"] = self._face(full, fr["pose"])
            frames.append(fr)
            self._clock_ms = ts
            i += 1
        cap.release()
        if not frames:
            raise ValueError(f"no decodable frames in {path}")
        meta = {"fps": fps, "width": w, "height": h, "frames": len(frames)}
        return frames, (w / h if h else 1.0), meta

    def _face(self, bgr, pose) -> list | None:
        """22 face points (contract.FACE_KEEP) in full-frame normalised coordinates, or None.

        The head is cropped from the full-resolution frame around the pose nose (side = 1.4 x the
        shoulder width, at least 1/6 of the frame height) and upscaled to 384 px for the landmarker."""
        import cv2

        from .contract import FACE_KEEP

        H, W = bgr.shape[:2]
        if pose is not None:
            nx, ny = pose[0][0] * W, pose[0][1] * H
            sw = abs(pose[11][0] - pose[12][0]) * W
            side = max(1.4 * sw, H / 6)
        else:
            nx, ny, side = W / 2, H / 3, H / 2
        x0, y0 = int(max(nx - side / 2, 0)), int(max(ny - side * 0.55, 0))
        x1, y1 = int(min(nx + side / 2, W)), int(min(ny + side * 0.45, H))
        if x1 - x0 < 16 or y1 - y0 < 16:
            return None
        crop = cv2.resize(bgr[y0:y1, x0:x1], (384, round(384 * (y1 - y0) / (x1 - x0))), interpolation=cv2.INTER_LINEAR)
        img = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        r = self.face.detect(img)
        if not r.face_landmarks:
            return None
        pts = r.face_landmarks[0]
        cw, ch = x1 - x0, y1 - y0
        return [[(x0 + pts[k].x * cw) / W, (y0 + pts[k].y * ch) / H, pts[k].z * cw / W] for k in FACE_KEEP]
