import { redirect } from "next/navigation";

import { loginUrlWithNext } from "@/lib/storefront-bridge";

export const dynamic = "force-dynamic";

type AccountLoginRedirectPageProps = {
  searchParams: Promise<{ next?: string }>;
};

function normalizeNext(nextValue: string | undefined) {
  if (!nextValue) {
    return "/account";
  }
  if (nextValue.startsWith("/")) {
    return nextValue;
  }
  return "/account";
}

export default async function AccountLoginRedirectPage({
  searchParams,
}: AccountLoginRedirectPageProps) {
  const params = await searchParams;
  const nextPath = normalizeNext(params.next);
  redirect(loginUrlWithNext(undefined, nextPath));
}
