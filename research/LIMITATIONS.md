# Limitations

* **No trained model on real data.** Every recognition feature is implemented and tested, but no model trained on authentic ISL data exists in this repository.
* **Vocabulary unverified.** All 200 entries come from INCLUDE folder names. A gloss is not an ISL sign: forms, regional variants and non-manual features need qualified review.
* **Category gaps.** INCLUDE lacks most everyday actions, food words and question words; the planning targets are not met.
* **INCLUDE signer IDs are unavailable**, so its official split cannot be proven signer-independent. INCLUDE was recorded at one institution in one city, which limits regional diversity.
* **Isolated signs only.** The system does not recognise continuous signing or produce grammatical translations; the communication composer only concatenates meanings.
* **No non-manual features** (facial expression, mouthing), which carry meaning in ISL.
* **MediaPipe dependence.** Landmark quality varies with lighting, skin tone, occlusion and camera. Depth (z) is relative.
* **Models are CPU-only NumPy implementations**, adequate for baselines but slow to train at scale; no TCN/Transformer yet.
* **Learning Academy does not assess signing quality**; it records quiz answers only.
* **Accessibility** was tested for keyboard focus, labels, contrast settings and mobile layout, but not with Deaf users or screen-reader users. User studies are needed.
* **The UI is in English only**; sign meanings support Hindi and Kannada.
