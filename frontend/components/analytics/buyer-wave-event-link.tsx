"use client";

import type { PropsWithChildren } from "react";

import {
  trackBuyerWaveEvent,
  type BuyerWaveEvent,
} from "@/lib/buyer-wave-analytics";

type BuyerWaveEventLinkProps = PropsWithChildren<{
  href: string;
  className?: string;
  event: BuyerWaveEvent;
  surface: string;
  payload?: Record<string, unknown>;
}>;

export function BuyerWaveEventLink({
  href,
  className,
  event,
  surface,
  payload = {},
  children,
}: BuyerWaveEventLinkProps) {
  function handleClick() {
    void trackBuyerWaveEvent(event, surface, payload);
  }

  return (
    <a href={href} className={className} onClick={handleClick}>
      {children}
    </a>
  );
}
