function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, "");
}

function normalizePath(path: string) {
  if (!path) {
    return "/";
  }
  return path.startsWith("/") ? path : `/${path}`;
}

const backendApiBase = trimTrailingSlash(
  process.env.BACKEND_API_URL || "http://backend:8000/api",
);

const derivedBackendOrigin = backendApiBase.endsWith("/api")
  ? backendApiBase.slice(0, -4)
  : backendApiBase;

const backendBridgeBase = trimTrailingSlash(
  process.env.BACKEND_ORIGIN || derivedBackendOrigin || "http://backend:8000",
);

const legacyStorefrontBase = trimTrailingSlash(
  process.env.LEGACY_STOREFRONT_URL || "http://localhost:8000",
);

export function backendApiUrl(path: string) {
  return `${backendApiBase}${normalizePath(path)}`;
}

export function backendBridgeUrl(path: string) {
  return `${backendBridgeBase}${normalizePath(path)}`;
}

export function legacyStorefrontUrl(path: string) {
  return `${legacyStorefrontBase}${normalizePath(path)}`;
}

export function loginUrlWithNext(loginUrl: string | null | undefined, nextPath: string) {
  const normalizedNext = normalizePath(nextPath);
  const fallbackLogin = "/legacy/account/login/";
  const source = (loginUrl || "").trim();
  const localhostHosts = new Set(["localhost", "127.0.0.1", "::1"]);

  const applyNextToRelativePath = (path: string) => {
    const relativeUrl = new URL(path, "http://local.invalid");
    relativeUrl.searchParams.set("next", normalizedNext);
    return `${relativeUrl.pathname}${relativeUrl.search}${relativeUrl.hash}`;
  };

  if (!source) {
    return applyNextToRelativePath(fallbackLogin);
  }

  if (source.startsWith("/")) {
    return applyNextToRelativePath(fallbackLogin);
  }

  try {
    const target = new URL(source, legacyStorefrontBase);
    if (localhostHosts.has(target.hostname)) {
      return applyNextToRelativePath(fallbackLogin);
    }
    target.searchParams.set("next", normalizedNext);
    return target.toString();
  } catch {
    return applyNextToRelativePath(fallbackLogin);
  }
}

export { backendApiBase, backendBridgeBase, legacyStorefrontBase };
