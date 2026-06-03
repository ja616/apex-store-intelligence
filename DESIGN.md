# APEX Store Intelligence - Architecture Design

APEX is a confidence-aware retail analytics platform that converts offline CCTV footage into operational intelligence.

## System Architecture

The architecture is explicitly designed around **Event Sourcing**, separating the heavy computer vision extraction (Offline Pipeline) from the semantic analysis (Analytics Engine).

### 1. Data Flow Pipeline

1. **Video Ingestion & Offline Processing**
   - The system ingests unseen CCTV footage (e.g. `CAM 1.mp4` ... `CAM 5.mp4`).
   - The **Detection Pipeline** processes frames to extract raw visitor bounding boxes.
   - The **Identity Persistence Engine** assigns persistent IDs to visitors, cross-referencing camera topology.
   - Outputs: Immutable Tracking Events (JSON).

2. **Event Sourcing (Ingestion API)**
   - Tracking Events are ingested into the **Event Ledger** (SQLite by default).
   - This ensures that detection logic can be re-run, or metrics recalculated, without reprocessing the video.

3. **Session Builder**
   - Consumes raw events to construct **Visitor Sessions**.
   - Handles re-entries, group entries, and staff exclusion.

4. **Analytics Engine & Conversion Attribution**
   - Calculates visitor counts, heatmaps, and anomalies.
   - Cross-references Visitor Sessions with the provided POS transaction CSV to compute deterministic offline conversion rates.

5. **Dashboard & API**
   - **FastAPI** serves metrics with mandatory confidence and reasoning fields.
   - **React/Vite** dashboard visualizes the data for executive overview.

## Core Differentiators

### A. Confidence Propagation
Every layer of the system attaches a confidence score and a human-readable explanation to its output.

- **Detection Confidence**: Box confidence from the YOLO/RT-DETR model.
- **Identity Confidence**: Computed from appearance similarity (OSNet) + temporal plausibility + topology constraints.
- **Metric Confidence**: Aggregated confidence. E.g., if a conversion is attributed to a low-confidence identity match, the overall conversion metric confidence drops, and the reason explicitly states why.

### B. Camera Topology Engine
Instead of treating cameras as isolated sensors, APEX builds a directed graph of the store's camera layout based on `Brigade Road - Store layoutc5f5d56.xlsx`.
- Nodes: Camera Zones (Entry, Floor, Billing, etc.).
- Edges: Plausible transition paths and expected minimum/maximum traversal times.
- Benefit: Prevents false merges (e.g., identity appearing at the Billing counter immediately after the Entry camera without traversing the Floor).

### C. Identity Persistence Engine
The most critical subsystem.
- Tracks individuals within a single camera view using ByteTrack.
- Re-identifies individuals across cameras and after occlusions using OSNet embeddings.
- Final identity assignment is a hybrid score: `Appearance + Temporal + Topology`.

### D. Conversion Attribution
Rather than estimating purchases via bounding box overlaps at the till, APEX correlates:
1. Visitor presence in the defined "Billing Zone".
2. The exact timestamp of transactions from the POS CSV.
3. A configurable temporal window.

## Alternatives Considered

- **Architecture**: Distributed Streaming (Kafka + Flink) vs Offline Batch -> Event API. 
  - *Decision*: Offline Batch -> Event API. 
  - *Why*: The requirement prioritizes robust handling of unseen videos and engineering judgment over unnecessary infrastructure complexity. Streaming adds points of failure for evaluation.

- **Tracking Database**: Vector Databases (Milvus/Pinecone) vs SQLite + Local Embedding Cache.
  - *Decision*: SQLite + Cache.
  - *Why*: Rule: "Do NOT use vector databases". An in-memory FAISS or simple matrix multiplication is sufficient for the scale of a single store's daily visitors, keeping the stack lean and reliable.

- **Anomaly Detection**: Black-box ML (Autoencoders) vs Rule-based Heuristics.
  - *Decision*: Rule-based Heuristics.
  - *Why*: Black-box models violate the explainability requirement. Rule-based anomalies (e.g., `QUEUE_SPIKE`, `STALE_FEED`) can explicitly state their trigger conditions in the API payload.
