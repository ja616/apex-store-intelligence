"""Populate the local SQLite database with sample events and POS transactions."""
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from apex.models.database import SessionLocal, init_db
from apex.models.events import Event, EventType
from apex.models.sessions import Session as SessionModel, ZoneVisit
from apex.models.visitors import Visitor
from apex.models.transactions import Transaction
from apex.analytics.conversion import ConversionAttributionEngine
from apex.session_builder import SessionBuilder

STORE_ID = "brigade-road-bangalore"
BASE_TIME = datetime.now() - timedelta(hours=4)

def create_sample_events(visitors):
    events = []
    
    # 15 customers who enter, browse, go to billing, and exit
    for i, vid in enumerate(visitors[:15]):
        offset = i * 600 # spaced out entries
        # Entry
        events.append(Event(
            event_id=str(uuid.uuid4()), store_id=STORE_ID, camera_id="CAM1", visitor_id=vid,
            event_type=EventType.PERSON_ENTERED.value, timestamp=BASE_TIME + timedelta(seconds=offset),
            confidence=0.92, identity_confidence=0.90, is_staff=False
        ))
        # Floor browsing
        events.append(Event(
            event_id=str(uuid.uuid4()), store_id=STORE_ID, camera_id="CAM2", visitor_id=vid,
            event_type=EventType.ZONE_TRANSITION.value, timestamp=BASE_TIME + timedelta(seconds=offset + 120),
            confidence=0.88, identity_confidence=0.85, is_staff=False
        ))
        events.append(Event(
            event_id=str(uuid.uuid4()), store_id=STORE_ID, camera_id="CAM3", visitor_id=vid,
            event_type=EventType.ZONE_TRANSITION.value, timestamp=BASE_TIME + timedelta(seconds=offset + 300),
            confidence=0.89, identity_confidence=0.86, is_staff=False
        ))
        # Billing Counter
        events.append(Event(
            event_id=str(uuid.uuid4()), store_id=STORE_ID, camera_id="CAM4", visitor_id=vid,
            event_type=EventType.BILLING_ZONE_ENTERED.value, timestamp=BASE_TIME + timedelta(seconds=offset + 480),
            confidence=0.90, identity_confidence=0.88, is_staff=False
        ))
        events.append(Event(
            event_id=str(uuid.uuid4()), store_id=STORE_ID, camera_id="CAM4", visitor_id=vid,
            event_type=EventType.BILLING_ZONE_EXITED.value, timestamp=BASE_TIME + timedelta(seconds=offset + 600),
            confidence=0.91, identity_confidence=0.89, is_staff=False
        ))
        # Exit
        events.append(Event(
            event_id=str(uuid.uuid4()), store_id=STORE_ID, camera_id="CAM1", visitor_id=vid,
            event_type=EventType.PERSON_EXITED.value, timestamp=BASE_TIME + timedelta(seconds=offset + 720),
            confidence=0.93, identity_confidence=0.91, is_staff=False
        ))

    # 3 staff members who are present in zones the whole time
    for i, vid in enumerate(visitors[15:18]):
        for hour in range(5):
            events.append(Event(
                event_id=str(uuid.uuid4()), store_id=STORE_ID, camera_id="CAM2", visitor_id=vid,
                event_type=EventType.PERSON_DETECTED.value, timestamp=BASE_TIME + timedelta(hours=hour),
                confidence=0.95, identity_confidence=0.95, is_staff=True
            ))

    # 7 customers who browse but don't convert (no billing visits, just exit)
    for i, vid in enumerate(visitors[18:]):
        offset = i * 800
        events.append(Event(
            event_id=str(uuid.uuid4()), store_id=STORE_ID, camera_id="CAM1", visitor_id=vid,
            event_type=EventType.PERSON_ENTERED.value, timestamp=BASE_TIME + timedelta(seconds=offset + 100),
            confidence=0.85, identity_confidence=0.80, is_staff=False
        ))
        events.append(Event(
            event_id=str(uuid.uuid4()), store_id=STORE_ID, camera_id="CAM2", visitor_id=vid,
            event_type=EventType.ZONE_TRANSITION.value, timestamp=BASE_TIME + timedelta(seconds=offset + 300),
            confidence=0.84, identity_confidence=0.81, is_staff=False
        ))
        events.append(Event(
            event_id=str(uuid.uuid4()), store_id=STORE_ID, camera_id="CAM1", visitor_id=vid,
            event_type=EventType.PERSON_EXITED.value, timestamp=BASE_TIME + timedelta(seconds=offset + 500),
            confidence=0.86, identity_confidence=0.82, is_staff=False
        ))

    return events

def main():
    print("Initialising database tables...")
    init_db()
    
    db: Session = SessionLocal()
    
    visitors = [str(uuid.uuid4()) for _ in range(25)]
    
    print("Generating sample visitor events...")
    events = create_sample_events(visitors)
    for e in events:
        db.add(e)
    db.commit()
    
    print("Generating sample visitors...")
    visitor_objs = []
    # 15 customers who enter, browse, go to billing, and exit
    for i, vid in enumerate(visitors[:15]):
        offset = i * 600
        visitor_objs.append(Visitor(
            visitor_id=vid,
            store_id=STORE_ID,
            first_seen=BASE_TIME + timedelta(seconds=offset),
            last_seen=BASE_TIME + timedelta(seconds=offset + 720),
            is_staff=False,
            staff_confidence=0.05,
            total_visits=1,
            identity_confidence=0.90,
        ))
    
    # 3 staff members who are present in zones the whole time
    for i, vid in enumerate(visitors[15:18]):
        visitor_objs.append(Visitor(
            visitor_id=vid,
            store_id=STORE_ID,
            first_seen=BASE_TIME,
            last_seen=BASE_TIME + timedelta(hours=4),
            is_staff=True,
            staff_confidence=0.98,
            staff_reason="Constant presence and behaviour profile matching staff templates.",
            total_visits=1,
            identity_confidence=0.95,
        ))

    # 7 customers who browse but don't convert (no billing visits, just exit)
    for i, vid in enumerate(visitors[18:]):
        offset = i * 800
        visitor_objs.append(Visitor(
            visitor_id=vid,
            store_id=STORE_ID,
            first_seen=BASE_TIME + timedelta(seconds=offset + 100),
            last_seen=BASE_TIME + timedelta(seconds=offset + 500),
            is_staff=False,
            staff_confidence=0.10,
            total_visits=1,
            identity_confidence=0.82,
        ))

    for v in visitor_objs:
        db.add(v)
    db.commit()
    
    print("Building sessions...")
    builder = SessionBuilder()
    sessions = builder.build_sessions(events)
    for s in sessions:
        db.add(s)
        for zv in s.zone_visits:
            db.add(zv)
    db.commit()
    
    print("Loading POS transactions from CSV...")
    engine = ConversionAttributionEngine()
    # We load transactions from the provided CSV file
    csv_path = "Brigade_Bangalore_10_April_26 (1)bc6219c.csv"
    
    # Read first few transactions to align dates/timestamps to current run time
    # so that our temporal correlation window matches perfectly.
    import pandas as pd
    df = pd.read_csv(csv_path)
    # Convert dates to match current date
    current_date_str = datetime.now().strftime("%d-%m-%Y")
    df['order_date'] = current_date_str
    
    # Distribute transaction times across the session times
    df['order_time'] = [
        (BASE_TIME + timedelta(seconds=i * 600 + 540)).strftime("%H:%M:%S")
        for i in range(len(df))
    ]
    
    temp_csv = "aligned_transactions.csv"
    df.to_csv(temp_csv, index=False)
    
    count = engine.load_transactions(temp_csv, STORE_ID, db)
    print(f"Loaded {count} transactions.")
    
    import os
    if os.path.exists(temp_csv):
        os.remove(temp_csv)
        
    print("Attributing transactions to visitor sessions...")
    attributions = engine.attribute_sessions(STORE_ID, db)
    attributed_count = sum(1 for r in attributions if r.attributed)
    print(f"Attributed {attributed_count} transactions to visitor sessions.")
    
    print("Database populated successfully!")
    db.close()

if __name__ == "__main__":
    main()
