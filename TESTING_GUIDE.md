# APEX Store Intelligence: Reviewer & Tester's Guide

Welcome to the **APEX Store Intelligence** verification suite. This guide provides a step-by-step roadmap to explore, test, and validate the platform.

APEX is a confidence-aware retail analytics platform tailored for the **Purplle cosmetics e-commerce brand**. It processes offline CCTV video feeds, merges identities across non-overlapping camera fields, filters out store staff, and attributes point-of-sale (POS) transactions to visitor journeys with explainable confidence intervals.



## 🚫 Zero Mock Data Policy

> [!IMPORTANT]
> **No Silent Mock Fallbacks:** In compliance with verification rules, all mock data fallback mechanisms have been deactivated in the main API requests when `VITE_USE_MOCK_DATA=false`. 
> If the backend FastAPI server goes offline, the frontend will not display mock numbers. Instead, a connection error banner will appear on each page, providing direct instructions on how to start the backend.

---

## ⚙️ Environment Setup & System Requirements

Ensure you have the following installed on your machine:
* Python 3.10 or higher
* Node.js (v18+) and npm
* OpenCV dependencies (`opencv-python-headless` is pre-configured in requirements)

### Step 1: Start the Backend FastAPI Server
From the project root directory, run:
```bash
# 1. Install required packages
pip install -r requirements.txt

# 2. Initialize database schema
python -c "from apex.models.database import init_db; init_db()"

# 3. Start API server on port 8000
python -m uvicorn apex.api.main:app --host 127.0.0.1 --port 8000 --reload
```
* **Verify**: Open `http://127.0.0.1:8000/docs` in your browser to view the interactive API swagger documentation.

### Step 2: Start the React Dashboard
From a new terminal in the `dashboard` directory:
```bash
# 1. Navigate to dashboard folder
cd dashboard

# 2. Install dependencies
npm install

# 3. Launch Vite development server
npm run dev
```
* **Verify**: Open `http://localhost:5173` in your browser. The dashboard should connect to your local backend API and load.

---

## 🧪 Verification Walkthrough (Step-by-Step)

Follow these phases to test the end-to-end functionality:

### Phase A: Run Automated Tests
Verify code correctness, edge-case coverage, and pipeline logic using the test suite:
```bash
python -m pytest
```
* **Expected Result**: All **57 tests** pass successfully, covering staff exclusion formulas, camera topology validation, session builders, and conversion attributions.

### Phase B: Seed the Database with Sample Data
To test conversion attribution and dashboard charts immediately with pre-calculated real-world visitor telemetry:
```bash
# This will clear any old database state and seed fresh mock-live data
python populate_sample.py
```
* **Expected Result**: The script drops any previous database state, loads the transaction POS CSV file, aligns dates to the current run time, and inserts **25 distinct visitor identities** (including 3 staff members) into the `visitors` database table. It then builds sessions and attributions, linking transactions to visitor journeys.
* **Verification**: In the **Live Visitor Metrics** page, you will now see all 25 active visitor profiles populate instantly, and in the **Journey Explorer** tab, you will see a detailed path breakdown without schema errors.

### Phase C: Test Ingestion with a New Video Clip
To verify the offline video processing pipeline with an unseen video clip:

1. Locate a video file (e.g. `CCTV Footage/CAM 1.mp4`).
2. Run the ingestion tool:
   ```bash
   # Usage: python ingest_video.py <path_to_video> <camera_id> [max_frames]
   python ingest_video.py "CCTV Footage/CAM 1.mp4" CAM1 200
   ```
   *(Specifying `200` limits processing to the first 200 frames for a rapid test run).*
3. **Verify Console Output**: The script will show live status, progress percentages, detected visitors, and event counts, then print a completion summary.
4. **Verify Dashboard Response**: Refresh the dashboard at `http://localhost:5173`. The newly processed visitor sessions and telemetry will appear under the **Live Visitors** and **Executive Overview** charts.

---

## 📊 Core Features to Verify in the Dashboard

| Tab / View | Key Context to Explore | Verification Point |
| :--- | :--- | :--- |
| **Executive Overview** | View visitor counts, dwell times, and conversion rates. | Check the **System Confidence Overview** strip at the bottom of the page. It details exactly how many sessions are high/low confidence. |
| **Live Visitor Metrics** | Live grid of tracked shoppers. | Toggle the **Showing Staff** filter. Watch the visitor count filter out employees flagged by uniform appearance and loitering duration. |
| **Conversion Funnel** | Shows stages: Entered Store $\to$ Browsed Aisle $\to$ Reached Billing $\to$ Purchased. | Hover over the steps to see the custom confidence value computed for each stage of the funnel. |
| **Store Heatmap** | High-occupancy zone alert flags. | Dwell time displays average checkout speeds, highlighting bottleneck areas. |
| **Identity Monitor** | Persistent tracking matching logs. | Displays cross-camera Re-ID tracking. Review the **Matching Explanation** column, which details why two sessions were merged (e.g., appearance + topological transition check). |
| **Journey Explorer** | Sequential camera paths. | Shows the top 5 shopper routes. Displays conversion rates per specific path, proving that browsing certain aisles increases purchase likelihood. |
| **System Health** | Camera statuses, FPS, and event freshness. | Verify camera degradation levels and database connection health logs. |
