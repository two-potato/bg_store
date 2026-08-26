import { redirect } from "next/navigation";

import { legacyStorefrontUrl } from "@/lib/storefront-bridge";

type TrackingRedirectPageProps = {
  params: Promise<{ id: string }>;
};

export const dynamic = "force-dynamic";

export default async function TrackingRedirectPage({
  params,
}: TrackingRedirectPageProps) {
  const { id } = await params;
  redirect(legacyStorefrontUrl(`/account/orders/${id}/tracking/`));
}
