// Mock data for all API endpoints
// Used as fallback when the backend is unavailable

export const STORE_ID = 'brigade-road-bangalore';

export const mockMetrics = {
  unique_visitors: 412,
  conversion_rate: 0.34,
  avg_dwell_seconds: 847,
  peak_hour: 15,
  metric_confidence: 0.91,
  reasoning: {
    sessions: 412,
    converted_sessions: 141,
    staff_excluded: 8,
    high_confidence_sessions: 381,
    low_confidence_sessions: 31,
  },
};

export const mockFunnel = {
  stages: [
    { stage: 'Entered Store', count: 412, confidence: 0.94 },
    { stage: 'Browsed (>2 min)', count: 318, confidence: 0.91 },
    { stage: 'Reached Billing Zone', count: 201, confidence: 0.88 },
    { stage: 'Purchased', count: 141, confidence: 0.89 },
  ],
  conversion_rate: 0.34,
  funnel_confidence: 0.91,
};

export const mockHeatmap = {
  zones: [
    { zone_id: 'entry', zone_name: 'Entry', visitor_count: 412, avg_dwell_seconds: 45, occupancy_pct: 0.65, camera_id: 'CAM1' },
    { zone_id: 'floor-a', zone_name: 'Floor A', visitor_count: 289, avg_dwell_seconds: 320, occupancy_pct: 0.78, camera_id: 'CAM2' },
    { zone_id: 'floor-b', zone_name: 'Floor B', visitor_count: 198, avg_dwell_seconds: 280, occupancy_pct: 0.52, camera_id: 'CAM3' },
    { zone_id: 'billing-a', zone_name: 'Billing A', visitor_count: 141, avg_dwell_seconds: 185, occupancy_pct: 0.88, camera_id: 'CAM4' },
    { zone_id: 'billing-b', zone_name: 'Billing B', visitor_count: 67, avg_dwell_seconds: 142, occupancy_pct: 0.41, camera_id: 'CAM5' },
  ],
  timestamp: new Date().toISOString(),
};

export const mockAnomalies = {
  anomalies: [
    {
      anomaly_id: 'anom-001',
      anomaly_type: 'QUEUE_SPIKE',
      severity: 'HIGH',
      confidence: 0.95,
      reason: 'Billing zone occupancy exceeded 5 people for 8 minutes',
      suggested_action: 'Open additional billing counter',
      detection_rule: 'queue_depth > 5 AND duration > 5 minutes',
      detected_at: new Date(Date.now() - 12 * 60000).toISOString(),
      camera_id: 'CAM4',
    },
    {
      anomaly_id: 'anom-002',
      anomaly_type: 'LOITERING',
      severity: 'MEDIUM',
      confidence: 0.82,
      reason: 'Visitor stayed in Floor-B for over 45 minutes without proceeding to billing',
      suggested_action: 'Send staff to assist the visitor',
      detection_rule: 'dwell_time > 45 min AND no_billing_visit',
      detected_at: new Date(Date.now() - 28 * 60000).toISOString(),
      camera_id: 'CAM3',
    },
    {
      anomaly_id: 'anom-003',
      anomaly_type: 'LOW_FOOTFALL',
      severity: 'LOW',
      confidence: 0.88,
      reason: 'Floor-A visitor count dropped 40% below hourly average',
      suggested_action: 'Review promotional displays in Floor-A',
      detection_rule: 'hourly_visitors < 0.6 * avg_hourly_visitors',
      detected_at: new Date(Date.now() - 55 * 60000).toISOString(),
      camera_id: 'CAM2',
    },
    {
      anomaly_id: 'anom-004',
      anomaly_type: 'TAILGATING',
      severity: 'HIGH',
      confidence: 0.78,
      reason: 'Multiple individuals entered simultaneously at entry gate',
      suggested_action: 'Review entry gate security protocol',
      detection_rule: 'simultaneous_entry > 3 AND gap < 0.5s',
      detected_at: new Date(Date.now() - 5 * 60000).toISOString(),
      camera_id: 'CAM1',
    },
    {
      anomaly_id: 'anom-005',
      anomaly_type: 'STAFF_ZONE_BREACH',
      severity: 'MEDIUM',
      confidence: 0.91,
      reason: 'Non-staff individual detected in restricted storage area',
      suggested_action: 'Alert security personnel immediately',
      detection_rule: 'visitor_in_restricted_zone AND NOT staff_id',
      detected_at: new Date(Date.now() - 3 * 60000).toISOString(),
      camera_id: 'CAM2',
    },
  ],
  total_active: 5,
};

export const mockVisitors = {
  visitors: [
    { visitor_id: 'VIS-8821', camera_id: 'CAM1', zone: 'Entry', dwell_seconds: 32, confidence: 0.97, is_staff: false, entered_at: new Date(Date.now() - 2 * 60000).toISOString() },
    { visitor_id: 'VIS-8815', camera_id: 'CAM2', zone: 'Floor A', dwell_seconds: 487, confidence: 0.91, is_staff: false, entered_at: new Date(Date.now() - 9 * 60000).toISOString() },
    { visitor_id: 'VIS-8809', camera_id: 'CAM3', zone: 'Floor B', dwell_seconds: 712, confidence: 0.76, is_staff: false, entered_at: new Date(Date.now() - 13 * 60000).toISOString() },
    { visitor_id: 'STAFF-001', camera_id: 'CAM4', zone: 'Billing A', dwell_seconds: 3600, confidence: 0.99, is_staff: true, entered_at: new Date(Date.now() - 60 * 60000).toISOString() },
    { visitor_id: 'VIS-8803', camera_id: 'CAM4', zone: 'Billing A', dwell_seconds: 185, confidence: 0.88, is_staff: false, entered_at: new Date(Date.now() - 5 * 60000).toISOString() },
    { visitor_id: 'VIS-8798', camera_id: 'CAM2', zone: 'Floor A', dwell_seconds: 924, confidence: 0.93, is_staff: false, entered_at: new Date(Date.now() - 16 * 60000).toISOString() },
    { visitor_id: 'VIS-8792', camera_id: 'CAM5', zone: 'Billing B', dwell_seconds: 142, confidence: 0.85, is_staff: false, entered_at: new Date(Date.now() - 3 * 60000).toISOString() },
    { visitor_id: 'STAFF-002', camera_id: 'CAM3', zone: 'Floor B', dwell_seconds: 5400, confidence: 0.99, is_staff: true, entered_at: new Date(Date.now() - 90 * 60000).toISOString() },
    { visitor_id: 'VIS-8786', camera_id: 'CAM1', zone: 'Entry', dwell_seconds: 18, confidence: 0.62, is_staff: false, entered_at: new Date(Date.now() - 1 * 60000).toISOString() },
    { visitor_id: 'VIS-8780', camera_id: 'CAM2', zone: 'Floor A', dwell_seconds: 340, confidence: 0.89, is_staff: false, entered_at: new Date(Date.now() - 7 * 60000).toISOString() },
    { visitor_id: 'VIS-8774', camera_id: 'CAM3', zone: 'Floor B', dwell_seconds: 510, confidence: 0.77, is_staff: false, entered_at: new Date(Date.now() - 11 * 60000).toISOString() },
    { visitor_id: 'VIS-8768', camera_id: 'CAM4', zone: 'Billing A', dwell_seconds: 245, confidence: 0.92, is_staff: false, entered_at: new Date(Date.now() - 6 * 60000).toISOString() },
  ],
  total_active: 12,
  staff_active: 2,
};

export const mockJourneys = {
  journeys: [
    {
      journey_id: 'J-001',
      path: ['Entry', 'Floor A', 'Billing A'],
      visitor_count: 89,
      avg_duration_seconds: 720,
      conversion_rate: 0.78,
      avg_confidence: 0.93,
    },
    {
      journey_id: 'J-002',
      path: ['Entry', 'Floor A', 'Floor B', 'Billing A'],
      visitor_count: 67,
      avg_duration_seconds: 1240,
      conversion_rate: 0.91,
      avg_confidence: 0.89,
    },
    {
      journey_id: 'J-003',
      path: ['Entry', 'Floor B', 'Floor A', 'Billing A'],
      visitor_count: 45,
      avg_duration_seconds: 1050,
      conversion_rate: 0.82,
      avg_confidence: 0.87,
    },
    {
      journey_id: 'J-004',
      path: ['Entry', 'Floor A', 'Exit'],
      visitor_count: 78,
      avg_duration_seconds: 380,
      conversion_rate: 0,
      avg_confidence: 0.91,
    },
    {
      journey_id: 'J-005',
      path: ['Entry', 'Billing B'],
      visitor_count: 34,
      avg_duration_seconds: 210,
      conversion_rate: 0.94,
      avg_confidence: 0.95,
    },
  ],
  total_journeys: 313,
};

export const mockHealth = {
  status: 'healthy',
  db_status: 'connected',
  model_status: 'loaded',
  event_freshness_seconds: 45,
  last_event_at: new Date(Date.now() - 45000).toISOString(),
  uptime_seconds: 14732,
  confidence: 0.99,
  cameras: [
    { camera_id: 'CAM1', status: 'online', zone: 'Entry', fps: 25, last_event_seconds: 12 },
    { camera_id: 'CAM2', status: 'online', zone: 'Floor A', fps: 25, last_event_seconds: 8 },
    { camera_id: 'CAM3', status: 'online', zone: 'Floor B', fps: 24, last_event_seconds: 15 },
    { camera_id: 'CAM4', status: 'online', zone: 'Billing A', fps: 25, last_event_seconds: 5 },
    { camera_id: 'CAM5', status: 'degraded', zone: 'Billing B', fps: 18, last_event_seconds: 42 },
  ],
};

export const mockIdentity = {
  identities: [
    { identity_id: 'ID-4421', matched_visitors: ['VIS-8821', 'VIS-8768'], matching_explanation: 'Appearance match: clothing + gait (0.94)', reentry_confidence: 0.94, is_reentry: true, reentry_gap_minutes: 47, first_seen: new Date(Date.now() - 3 * 3600000).toISOString(), last_seen: new Date(Date.now() - 5 * 60000).toISOString() },
    { identity_id: 'ID-4415', matched_visitors: ['VIS-8815'], matching_explanation: 'Single session, no reentry', reentry_confidence: 0.97, is_reentry: false, reentry_gap_minutes: 0, first_seen: new Date(Date.now() - 9 * 60000).toISOString(), last_seen: new Date(Date.now() - 9 * 60000).toISOString() },
    { identity_id: 'ID-4409', matched_visitors: ['VIS-8809', 'VIS-8774'], matching_explanation: 'Appearance match: height + clothing (0.82)', reentry_confidence: 0.82, is_reentry: true, reentry_gap_minutes: 22, first_seen: new Date(Date.now() - 2 * 3600000).toISOString(), last_seen: new Date(Date.now() - 11 * 60000).toISOString() },
    { identity_id: 'STAFF-001', matched_visitors: ['STAFF-001'], matching_explanation: 'Staff badge detected (0.99)', reentry_confidence: 0.99, is_reentry: false, is_staff: true, reentry_gap_minutes: 0, first_seen: new Date(Date.now() - 60 * 60000).toISOString(), last_seen: new Date().toISOString() },
    { identity_id: 'ID-4398', matched_visitors: ['VIS-8798', 'VIS-8780'], matching_explanation: 'Partial match: gait only (0.71)', reentry_confidence: 0.71, is_reentry: true, reentry_gap_minutes: 9, first_seen: new Date(Date.now() - 16 * 60000).toISOString(), last_seen: new Date(Date.now() - 7 * 60000).toISOString() },
  ],
  total_identities: 5,
  reentry_count: 3,
  staff_excluded: 2,
};

// Sparkline data for KPI cards (last 7 hours)
export const mockSparklines = {
  visitors: [38, 45, 52, 61, 78, 82, 56, 72, 89, 65, 70, 58, 76, 92],
  conversion: [0.28, 0.31, 0.29, 0.35, 0.38, 0.34, 0.30, 0.32, 0.36, 0.33, 0.37, 0.34, 0.35, 0.34],
  dwell: [620, 690, 750, 810, 870, 850, 820, 790, 840, 860, 830, 847, 855, 847],
  anomalies: [0, 1, 0, 2, 1, 3, 2, 4, 3, 5, 4, 5, 5, 5],
};

// Live ticker events
export const generateTickerEvents = () => {
  const events = [
    { id: 1, type: 'ENTRY', visitor_id: 'VIS-8821', zone: 'Entry', time: 'Just now', confidence: 0.97 },
    { id: 2, type: 'EXIT', visitor_id: 'VIS-8710', zone: 'Billing A', time: '1m ago', confidence: 0.92 },
    { id: 3, type: 'ZONE_CHANGE', visitor_id: 'VIS-8815', zone: 'Floor A → Floor B', time: '2m ago', confidence: 0.89 },
    { id: 4, type: 'ENTRY', visitor_id: 'VIS-8786', zone: 'Entry', time: '2m ago', confidence: 0.62 },
    { id: 5, type: 'PURCHASE', visitor_id: 'VIS-8803', zone: 'Billing A', time: '3m ago', confidence: 0.88 },
    { id: 6, type: 'EXIT', visitor_id: 'VIS-8754', zone: 'Entry', time: '4m ago', confidence: 0.95 },
    { id: 7, type: 'ZONE_CHANGE', visitor_id: 'VIS-8792', zone: 'Floor A → Billing B', time: '5m ago', confidence: 0.85 },
    { id: 8, type: 'ANOMALY', visitor_id: 'CAM4', zone: 'Billing A', time: '12m ago', confidence: 0.95 },
    { id: 9, type: 'ENTRY', visitor_id: 'VIS-8780', zone: 'Entry', time: '7m ago', confidence: 0.89 },
    { id: 10, type: 'EXIT', visitor_id: 'VIS-8701', zone: 'Entry', time: '8m ago', confidence: 0.91 },
    { id: 11, type: 'PURCHASE', visitor_id: 'VIS-8768', zone: 'Billing A', time: '6m ago', confidence: 0.92 },
    { id: 12, type: 'ZONE_CHANGE', visitor_id: 'VIS-8774', zone: 'Floor B → Billing A', time: '10m ago', confidence: 0.77 },
  ];
  return events;
};
