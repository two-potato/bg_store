export const siteName = "Servio";

export function siteUrl() {
  return process.env.SITE_URL || "http://localhost:8080";
}
