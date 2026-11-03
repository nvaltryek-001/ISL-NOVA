# Privacy notice (template)

> This is a technical privacy notice describing how the software handles data. Before a public deployment, the operator must adapt it with their legal identity, contact details, lawful basis and applicable law (e.g. India's Digital Personal Data Protection Act, 2023), and have it reviewed by a qualified professional.

**What we collect**
* **Account data:** email, display name, password hash, roles, preferences.
* **Live recognition:** hand and pose *landmark coordinates* only. Camera video is processed on your device and is not uploaded. Results are saved to your history only when you choose to save them.
* **Video analysis:** the file you upload, kept for at most 24 hours (configurable) or until you delete it.
* **Dataset contributors (signers):** a pseudonymous code, optional dominant hand, age band, region and hearing status; the recordings you consent to; your consent record.
* **Usage records:** recognition history, learning attempts, bookmarks, phrases, feedback, and an audit log of administrative actions.

**Why:** to provide recognition, learning and communication features and, only with explicit consent, to build and evaluate ISL recognition models.

**Your choices:** delete history items or all history; delete analysis uploads at any time; signers may withdraw consent at any time, which erases their recordings.

**Sharing:** no data is sold or shared with third parties. The browser loads MediaPipe code and models from jsDelivr and Google Cloud Storage; operators can self-host them.

**Security:** see [SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md).
