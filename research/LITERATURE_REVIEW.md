# Literature review

Only sources whose bibliographic details were checked are listed. Findings are summarised conservatively; consult the papers for detail.

## ISL datasets and benchmarks
* **INCLUDE** (Sridhar, Ganesan, Kumar, Khapra, ACM MM 2020, doi:10.1145/3394171.3413528). 263 isolated ISL word signs in 15 categories, 4,292 videos recorded with deaf students in Chennai, plus a 50-class subset (INCLUDE-50); CC BY 4.0 on Zenodo. The accompanying code extracts MediaPipe hand and pose keypoints and trains LSTM, Transformer and XGBoost models. *Used by ISL NOVA as the vocabulary and first data source.*
* **iSign** (Joshi, Mohanty, Kanakanti, Mangla, Choudhary, Barbate, Modi, Findings of ACL 2024, pp. 10827–10844, doi:10.18653/v1/2024.findings-acl.643). A large ISL–English video/sentence benchmark with five tasks (SignVideo2Text, SignPose2Text, Text2Pose, word prediction, sign semantics). Released under CC BY-NC-SA 4.0 with gated access.

## Other sign-language recognition work
* **WLASL** (Li, Rodriguez Opazo, Yu, Li, WACV 2020, arXiv:1910.11006). A large word-level American Sign Language dataset comparing appearance-based and pose-based methods. Relevant as a methodological reference for isolated-sign recognition at scale.

## Methods used in ISL NOVA
* **LSTM**: Hochreiter & Schmidhuber, *Neural Computation* 9(8), 1997, doi:10.1162/neco.1997.9.8.1735.
* **GRU**: Cho et al., EMNLP 2014, arXiv:1406.1078.
* **Dynamic time warping**: Sakoe & Chiba, *IEEE Trans. ASSP* 26(1), 1978, doi:10.1109/TASSP.1978.1163055.
* **Temperature scaling for calibration**: Guo, Pleiss, Sun, Weinberger, ICML 2017, arXiv:1706.04599.
* **Maximum-softmax-probability baseline for unknown inputs**: Hendrycks & Gimpel, ICLR 2017, arXiv:1610.02136.
* **Hand landmarks**: Zhang et al., "MediaPipe Hands: On-device Real-time Hand Tracking", arXiv:2006.10214, 2020.
* **Candidates not yet implemented**: TCN (Bai, Kolter, Koltun, arXiv:1803.01271, 2018); Transformer (Vaswani et al., NeurIPS 2017, arXiv:1706.03762).

## Gaps this project addresses
Public ISL resources rarely provide **signer IDs** (needed for signer-independent evaluation), explicit **consent scopes**, or **calibrated rejection** of unknown signs. ISL NOVA's data model and evaluation protocol are designed around these three gaps.

_TBD: a systematic review of ISL recognition papers from 2015–2026 (search strategy and inclusion criteria to be defined in RESEARCH_QUESTIONS.md)._
