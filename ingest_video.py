"""CLI tool to ingest and process a video clip through the APEX API backend."""
import sys
import os
import time

try:
    import requests
except ImportError:
    print("Error: 'requests' library is not installed. Please run: pip install requests")
    sys.exit(1)

def main():
    if len(sys.argv) < 3:
        print("APEX Video Ingestion Tool")
        print("-------------------------")
        print("Usage:")
        print("  python ingest_video.py <path_to_video> <camera_id> [max_frames]")
        print("\nExamples:")
        print("  python ingest_video.py \"CCTV Footage/CAM 1.mp4\" CAM1")
        print("  python ingest_video.py \"CCTV Footage/CAM 4.mp4\" CAM4 200  (processes first 200 frames)")
        sys.exit(1)
        
    video_path = sys.argv[1]
    camera_id = sys.argv[2]
    max_frames = int(sys.argv[3]) if len(sys.argv) > 3 else None
    
    if not os.path.exists(video_path):
        print(f"Error: Video file not found: {video_path}")
        sys.exit(1)
        
    url = "http://127.0.0.1:8000/api/v1/process/video"
    print(f"Uploading {video_path} for camera {camera_id}...")
    
    try:
        with open(video_path, 'rb') as f:
            files = {'file': f}
            data = {
                'camera_id': camera_id,
                'store_id': 'brigade-road-bangalore'
            }
            if max_frames is not None:
                data['max_frames'] = max_frames
                
            response = requests.post(url, files=files, data=data)
            
        if response.status_code != 200:
            print(f"Failed to submit video: {response.status_code} - {response.text}")
            sys.exit(1)
            
        res_data = response.json()
        job_id = res_data['job_id']
        print(f"Job successfully created! Job ID: {job_id}")
        print("Polling job progress...")
        
        status_url = f"http://127.0.0.1:8000/api/v1/process/jobs/{job_id}"
        
        while True:
            status_resp = requests.get(status_url)
            if status_resp.status_code != 200:
                print(f"\nFailed to fetch job status: {status_resp.status_code}")
                break
                
            status_data = status_resp.json()
            status = status_data['status']
            progress = status_data['progress_pct']
            events = status_data['events_generated']
            visitors = status_data['visitors_detected']
            
            sys.stdout.write(f"\rStatus: {status.upper().ljust(8)} | Progress: {progress:.1f}% | Events: {events} | Visitors: {visitors}")
            sys.stdout.flush()
            
            if status == "done":
                print(f"\n\nSuccess! Processing finished.")
                print(f"Generated {events} tracking events.")
                print(f"Identified {visitors} unique visitor paths.")
                print("Dashboard has been refreshed with this data.")
                break
            elif status == "failed":
                print(f"\n\nProcessing failed: {status_data.get('error')}")
                break
                
            time.sleep(2)
            
    except requests.exceptions.ConnectionError:
        print("\nError: Could not connect to FastAPI server. Make sure it is running on http://127.0.0.1:8000")
        sys.exit(1)

if __name__ == "__main__":
    main()
