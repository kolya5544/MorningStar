import { useEffect } from "react";

type SeoConfig = {
  title: string;
  description: string;
  canonicalPath?: string;
  robots?: string;
  image?: string;
  type?: "website" | "article";
  jsonLd?: Record<string, unknown>;
};

function siteUrl() {
  const configured = import.meta.env.VITE_SITE_URL?.trim();
  const base = configured || window.location.origin;
  return base.endsWith("/") ? base.slice(0, -1) : base;
}

function upsertMeta(attr: "name" | "property", key: string, content: string) {
  let element = document.head.querySelector<HTMLMetaElement>(`meta[${attr}="${key}"]`);
  if (!element) {
    element = document.createElement("meta");
    element.setAttribute(attr, key);
    document.head.appendChild(element);
  }
  element.setAttribute("content", content);
}

function upsertCanonical(href: string) {
  let element = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (!element) {
    element = document.createElement("link");
    element.setAttribute("rel", "canonical");
    document.head.appendChild(element);
  }
  element.setAttribute("href", href);
}

function upsertJsonLd(payload: Record<string, unknown>) {
  let element = document.head.querySelector<HTMLScriptElement>('script[data-seo="json-ld"]');
  if (!element) {
    element = document.createElement("script");
    element.type = "application/ld+json";
    element.dataset.seo = "json-ld";
    document.head.appendChild(element);
  }
  element.textContent = JSON.stringify(payload);
}

export function useSeo({
  title,
  description,
  canonicalPath,
  robots = "index,follow",
  image = "/bg.jpg",
  type = "website",
  jsonLd,
}: SeoConfig) {
  useEffect(() => {
    document.title = title;

    const canonical = `${siteUrl()}${canonicalPath ?? window.location.pathname}`;
    const fullImage = image.startsWith("http") ? image : `${siteUrl()}${image}`;

    upsertMeta("name", "description", description);
    upsertMeta("name", "robots", robots);
    upsertMeta("property", "og:title", title);
    upsertMeta("property", "og:description", description);
    upsertMeta("property", "og:type", type);
    upsertMeta("property", "og:url", canonical);
    upsertMeta("property", "og:image", fullImage);
    upsertMeta("name", "twitter:card", "summary_large_image");
    upsertMeta("name", "twitter:title", title);
    upsertMeta("name", "twitter:description", description);
    upsertMeta("name", "twitter:image", fullImage);
    upsertCanonical(canonical);

    if (jsonLd) {
      upsertJsonLd(jsonLd);
    } else {
      const existing = document.head.querySelector<HTMLScriptElement>('script[data-seo="json-ld"]');
      existing?.remove();
    }
  }, [canonicalPath, description, image, jsonLd, robots, title, type]);
}
