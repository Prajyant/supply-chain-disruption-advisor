/**
 * Shipment analysis preloader.
 *
 * Triggers background analysis of all shipments on app load so that
 * when a user navigates to a shipment detail page, the analysis is
 * already cached on the backend and loads instantly.
 */
import { shipmentApi } from './api';
import { loadDemoShipments } from './shipmentData';

let preloadTriggered = false;

/**
 * Trigger preloading of all shipment analyses.
 * Safe to call multiple times — only runs once.
 */
export async function triggerShipmentPreload(): Promise<void> {
  if (preloadTriggered) return;
  preloadTriggered = true;

  try {
    const shipments = await loadDemoShipments();
    if (shipments.length === 0) return;

    // Send all shipments to the backend for background analysis
    await shipmentApi.preloadAnalyses(shipments);
  } catch (err) {
    // Non-critical — preload failure just means on-demand analysis
    console.warn('[Preloader] Shipment preload failed:', err);
    preloadTriggered = false; // Allow retry
  }
}

/**
 * Try to get a preloaded analysis for a shipment.
 * Returns null if not yet available (caller should fall back to live analysis).
 */
export async function getPreloadedAnalysis(shipmentId: string): Promise<any | null> {
  try {
    const res = await shipmentApi.getPreloadedAnalysis(shipmentId);
    return res.data;
  } catch {
    return null;
  }
}
