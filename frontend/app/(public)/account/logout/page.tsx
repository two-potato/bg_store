import { redirect } from "next/navigation";

import { legacyStorefrontUrl } from "@/lib/storefront-bridge";

export const dynamic = "force-dynamic";

export default function AccountLogoutRedirectPage() {
  redirect(legacyStorefrontUrl("/account/logout/"));
}
