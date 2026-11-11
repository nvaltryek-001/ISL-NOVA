"""Versioned feature contract shared by training and inference.

Any change to feature order, dimensionality, normalisation or sequence length
MUST bump ``CONTRACT_VERSION``. Models record the contract version they were
trained with, and the inference service refuses to load a model whose contract
differs from the running code. The TypeScript port in
``frontend/src/lib/features.ts`` is checked against this module by a parity
fixture (see ``ml/tests/test_feature_parity_fixture.py``).
"""

from __future__ import annotations

CONTRACT_ID = "isl-nova-fc"
CONTRACT_VERSION = "1.0.0"
CONTRACT_NAME = f"{CONTRACT_ID}-{CONTRACT_VERSION}"

EXTRACTOR = "mediapipe-tasks-vision (HandLandmarker + PoseLandmarker)"
NOMINAL_FPS = 30
SEQUENCE_LENGTH = 32  # frames after temporal resampling
MIN_HAND_FRAME_RATIO = 0.25  # below this the input is "insufficient_input"
MIN_RAW_FRAMES = 8

HAND_POINTS = 21
# MediaPipe Pose indices kept (upper body only; face mesh is NOT used).
POSE_KEEP = [0, 11, 12, 13, 14, 15, 16, 23, 24]
POSE_NAMES = [
    "nose", "l_shoulder", "r_shoulder", "l_elbow", "r_elbow",
    "l_wrist", "r_wrist", "l_hip", "r_hip",
]
FINGERTIPS = [4, 8, 12, 16, 20]
# (a, b, c) triplets: angle at b between segments b->a and b->c.
FINGER_JOINTS = [
    (0, 1, 2), (1, 2, 3), (2, 3, 4),        # thumb
    (0, 5, 6), (5, 6, 7), (6, 7, 8),        # index
    (0, 9, 10), (9, 10, 11), (10, 11, 12),  # middle
    (0, 13, 14), (13, 14, 15), (14, 15, 16),  # ring
    (0, 17, 18), (17, 18, 19), (18, 19, 20),  # little
]

# Feature blocks, in order. (name, size)
BLOCKS: list[tuple[str, int]] = [
    ("left_hand_local", HAND_POINTS * 3),
    ("right_hand_local", HAND_POINTS * 3),
    ("wrists_body", 6),
    ("pose_body", len(POSE_KEEP) * 3),
    ("two_hand", 6),
    ("left_angles", len(FINGER_JOINTS)),
    ("right_angles", len(FINGER_JOINTS)),
    ("presence", 3),
    ("wrists_velocity", 6),
]
FEATURE_DIM = sum(n for _, n in BLOCKS)


def feature_names() -> list[str]:
    names: list[str] = []
    for side in ("left", "right"):
        names += [f"{side}_hand_{i}_{a}" for i in range(HAND_POINTS) for a in "xyz"]
    names += [f"{s}_wrist_body_{a}" for s in ("left", "right") for a in "xyz"]
    names += [f"pose_{n}_{a}" for n in POSE_NAMES for a in "xyz"]
    names += ["wrist_to_wrist"] + [f"tip{t}_pair_dist" for t in FINGERTIPS]
    for side in ("left", "right"):
        names += [f"{side}_angle_{a}_{b}_{c}" for a, b, c in FINGER_JOINTS]
    names += ["left_present", "right_present", "pose_present"]
    names += [f"{s}_wrist_vel_{a}" for s in ("left", "right") for a in "xyz"]
    return names


def as_dict() -> dict:
    return {
        "id": CONTRACT_ID,
        "version": CONTRACT_VERSION,
        "name": CONTRACT_NAME,
        "extractor": EXTRACTOR,
        "nominal_fps": NOMINAL_FPS,
        "sequence_length": SEQUENCE_LENGTH,
        "feature_dim": FEATURE_DIM,
        "blocks": [{"name": n, "size": s} for n, s in BLOCKS],
        "feature_names": feature_names(),
        "pose_indices": POSE_KEEP,
        "min_hand_frame_ratio": MIN_HAND_FRAME_RATIO,
        "min_raw_frames": MIN_RAW_FRAMES,
        "normalisation": (
            "x multiplied by image aspect (w/h); body frame = shoulder midpoint "
            "origin, shoulder width scale (fallback: hands bounding box); hand "
            "local frame = wrist origin, wrist->middle-MCP scale"
        ),
        "missing_values": "absent hand/pose -> zeros in its block, presence flag 0",
        "resampling": "linear interpolation over frame index to sequence_length",
        "model_input": "float32 array [sequence_length, feature_dim]",
        "non_manual_features": "none (face landmarks are not used in v1.0.0)",
    }


assert len(feature_names()) == FEATURE_DIM


# --------------------------------------------------------------------------- contract 2.0.0: + face
# isl-nova-fc-2.0.0 = the 204 features of 1.0.0 followed by a non-manual (face) block.
# Frames carry ``face``: the 22 MediaPipe FaceLandmarker points below, in this order.
CONTRACT_V2_VERSION = "2.0.0"
CONTRACT_V2_NAME = f"{CONTRACT_ID}-{CONTRACT_V2_VERSION}"
FACE_MODEL = "mediapipe-tasks-vision FaceLandmarker (478 points; 22 kept)"
FACE_KEEP = [1, 70, 105, 107, 336, 334, 300, 33, 133, 159, 145, 362, 263, 386, 374, 61, 291, 0, 17, 13, 14, 152]
FACE_NAMES = ["nose_tip", "l_brow_out", "l_brow_mid", "l_brow_in", "r_brow_out", "r_brow_mid", "r_brow_in",
              "l_eye_out", "l_eye_in", "l_eye_top", "l_eye_bottom", "r_eye_in", "r_eye_out", "r_eye_top",
              "r_eye_bottom", "mouth_l", "mouth_r", "lip_top_out", "lip_bottom_out", "lip_top_in", "lip_bottom_in",
              "chin"]
# derived measures, all divided by the eye-corner distance (l_eye_out..r_eye_out)
FACE_DERIVED = ["mouth_open", "mouth_width", "l_brow_raise", "r_brow_raise", "l_eye_open", "r_eye_open"]
FACE_DIM = len(FACE_KEEP) * 2 + len(FACE_DERIVED) + 1  # x,y per point + derived + face presence
SUPPORTED = {CONTRACT_VERSION: FEATURE_DIM, CONTRACT_V2_VERSION: FEATURE_DIM + FACE_DIM}


def dim_for(version: str) -> int:
    if version not in SUPPORTED:
        raise ValueError(f"unsupported feature contract {version!r}; supported: {sorted(SUPPORTED)}")
    return SUPPORTED[version]


def name_for(version: str) -> str:
    dim_for(version)
    return f"{CONTRACT_ID}-{version}"
