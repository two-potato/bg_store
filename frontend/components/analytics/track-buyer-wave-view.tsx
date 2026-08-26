"use client";

import { useEffect, useRef } from "react";

import {
  trackBuyerWaveEvent,
  type BuyerWaveEvent,
} from "@/lib/buyer-wave-analytics";

type TrackBuyerWaveViewProps = {
  event: BuyerWaveEvent;
  surface: string;
  payload?: Record<string, unknown>;
};

export function TrackBuyerWaveView({
  event,
  surface,
  payload = {},
}: TrackBuyerWaveViewProps) {
  const sentRef = useRef(false);

  useEffect(() => {
    if (sentRef.current) {
      return;
    }
    sentRef.current = true;
    void trackBuyerWaveEvent(event, surface, payload);
  }, [event, surface, payload]);

  return null;
}
