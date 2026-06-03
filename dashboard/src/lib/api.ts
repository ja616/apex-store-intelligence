import {
  mockMetrics,
  mockFunnel,
  mockHeatmap,
  mockAnomalies,
  mockVisitors,
  mockJourneys,
  mockHealth,
  mockIdentity,
} from './mock-data';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
const STORE_ID = import.meta.env.VITE_STORE_ID || 'brigade-road-bangalore';
const USE_MOCK = import.meta.env.VITE_USE_MOCK_DATA === 'true';

async function fetchWithFallback<T>(url: string, fallback: T): Promise<T> {
  if (USE_MOCK) return fallback;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timeout);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    return await res.json() as T;
  } catch (error) {
    clearTimeout(timeout);
    console.error(`[API] Fetch failed for: ${url}`, error);
    throw error;
  }
}

export const api = {
  getMetrics: () =>
    fetchWithFallback(`${BASE_URL}/stores/${STORE_ID}/metrics`, mockMetrics),

  getFunnel: () =>
    fetchWithFallback(`${BASE_URL}/stores/${STORE_ID}/funnel`, mockFunnel),

  getHeatmap: () =>
    fetchWithFallback(`${BASE_URL}/stores/${STORE_ID}/heatmap`, mockHeatmap),

  getAnomalies: () =>
    fetchWithFallback(`${BASE_URL}/stores/${STORE_ID}/anomalies`, mockAnomalies),

  getVisitors: () =>
    fetchWithFallback(`${BASE_URL}/stores/${STORE_ID}/visitors`, mockVisitors),

  getJourneys: () =>
    fetchWithFallback(`${BASE_URL}/stores/${STORE_ID}/journeys`, mockJourneys),

  getHealth: () =>
    fetchWithFallback(`${BASE_URL}/health`, mockHealth),

  getIdentity: () =>
    fetchWithFallback(`${BASE_URL}/stores/${STORE_ID}/identity`, mockIdentity),

  getRecentEvents: () =>
    fetchWithFallback(`${BASE_URL}/events/recent?store_id=${STORE_ID}`, []),
};

export { STORE_ID };
