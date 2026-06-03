# APEX Store Intelligence - Technical Choices

This document outlines the major architectural and engineering decisions made during the design of APEX. Each choice is defended in the context of the Purplle Store Intelligence Challenge rubric, prioritizing functional correctness, explainability, and edge-case handling over unnecessary complexity.

---

## 1. Object Detection Model: YOLOv11n vs RT-DETR

### Option A: YOLOv11n (Ultralytics)
A highly optimized, state-of-the-art CNN-based object detector.
- **Pros**: Extremely fast inference, low VRAM footprint, mature ecosystem, excellent out-of-the-box performance for human detection.
- **Cons**: Can struggle slightly with heavy occlusion compared to transformer-based architectures.

### Option B: RT-DETR
A Real-Time DEtection TRansformer.
- **Pros**: End-to-end detection without NMS, handles dense scenes and occlusions exceptionally well.
- **Cons**: Heavier compute requirements, less mature ecosystem, slightly slower than YOLOv11n on edge hardware.

### Final Decision: Benchmarking Required (Phase 3)
*Reasoning*: While YOLOv11n is the industry standard for speed, the challenge footage may contain high-occlusion scenarios where RT-DETR's lack of NMS provides a distinct advantage. We will empirically benchmark both models on a representative subset of the provided footage (evaluating Entry Accuracy, Exit Accuracy, and Speed) before finalizing the detector.

### Failure Modes & Scalability
If RT-DETR is chosen but proves too slow on reviewer machines, we risk failing the "production readiness / execution" metric. To mitigate this, we will ensure YOLOv11n remains a configurable fallback.

---

## 2. Multi-Object Tracking: ByteTrack vs DeepSORT

### Option A: ByteTrack
Associates almost every detection box (even low confidence) by utilizing spatial constraints.
- **Pros**: State-of-the-art MOTA, exceptionally fast (simple Kalman filter + IoU/ReID), recovers well from brief occlusions without relying heavily on expensive appearance embeddings for every frame.
- **Cons**: Prone to ID switches if frame rates drop significantly or if cameras have huge blind spots.

### Option B: DeepSORT
The classic tracking algorithm relying heavily on deep appearance features.
- **Pros**: Robust long-term tracking within a single camera if appearance is highly distinct.
- **Cons**: Slower, often overkill for intra-camera tracking where spatial heuristics (IoU) are sufficient.

### Final Decision: ByteTrack
*Reasoning*: ByteTrack handles the high-frame-rate, intra-camera tracking flawlessly. We explicitly decouple intra-camera tracking (ByteTrack) from inter-camera Re-Identification (OSNet). DeepSORT conflates the two, making it harder to inject our Camera Topology logic.

### Failure Modes & Scalability
ByteTrack can fail during extended occlusions within the same camera. We mitigate this by passing broken tracklets to our Identity Persistence Engine, which acts as a higher-level ReID fallback.

---

## 3. Re-Identification Embedding: OSNet vs Tracking-Only

### Option A: OSNet (Omni-Scale Network)
A lightweight CNN designed specifically for person Re-Identification, capturing both global and local features.
- **Pros**: Highly discriminative for clothing and appearance, robust to viewpoint changes (crucial for CCTV).
- **Cons**: Adds a second network pass after detection, increasing computational load.

### Option B: Tracking-Only (No ReID)
Relying purely on spatial overlap (IoU) and Entry/Exit heuristics.
- **Pros**: Extremely fast.
- **Cons**: Completely fails at cross-camera tracking and long-term re-entry.

### Final Decision: OSNet + Topology Constraints
*Reasoning*: Solving the Identity Persistence problem is impossible without a robust ReID model. OSNet provides the appearance vector. However, appearance alone is prone to false positives (e.g., two people wearing uniform-like black shirts). Therefore, OSNet embeddings are fused with Camera Topology (is this transition physically possible?) and Temporal Constraints (did they appear too quickly?).

### Failure Modes & Scalability
Appearance collapse (uniforms) is the primary failure mode. The Camera Topology graph directly mitigates this.

---

## 4. Anomaly Detection: Rule-Based vs ML Black-Box

### Option A: ML Black-Box (e.g., Autoencoders on Event Streams)
- **Pros**: Can discover unknown unknown patterns.
- **Cons**: Completely unexplainable. Violates the "Explainability" mandate. Cannot easily output a deterministic `reason`.

### Option B: Rule-Based Heuristics
Explicitly defining anomalies (e.g., `QUEUE_SPIKE`, `STALE_FEED`, `CONVERSION_DROP`).
- **Pros**: 100% explainable. We can attach precise confidence and reasoning (e.g., "Queue depth exceeded 5 people for 10 minutes").
- **Cons**: Requires manual tuning of thresholds.

### Final Decision: Rule-Based Heuristics
*Reasoning*: The rubric prioritizes clear reasoning. A rule-based Anomaly Engine directly fulfills the requirement for explainable alerts, generating outputs that are immediately understandable by store operations teams.

---

## 5. Dashboard Framework: React/Vite vs Streamlit

### Option A: Streamlit
- **Pros**: Extremely fast to build for Python engineers.
- **Cons**: Feels like a data science prototype. Lacks the polish of a true enterprise SaaS application.

### Option B: React + Vite + Tailwind + shadcn/ui
- **Pros**: Enterprise-grade aesthetics. Highly customizable, responsive, and reviewer-optimized.
- **Cons**: Requires context switching to TypeScript/Node ecosystem.

### Final Decision: React + Vite + Tailwind + shadcn/ui
*Reasoning*: The dashboard is the primary interface for reviewers. First impressions matter. A highly polished React dashboard immediately signals production readiness and engineering maturity, maximizing the score for the dashboard bonus component.
