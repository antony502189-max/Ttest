export type SupportedLocale = "es-ES" | "ru-RU" | "en-GB";

export function currentLocale(): SupportedLocale {
  let language = typeof document !== "undefined" ? document.documentElement.lang : "";
  if (typeof localStorage !== "undefined") {
    try {
      const stored = localStorage.getItem("112233:language:v1");
      if (stored === "es" || stored === "ru" || stored === "en") language = stored;
    } catch {
      // Document language remains the fallback when storage is unavailable.
    }
  }
  return language === "ru" ? "ru-RU" : language === "en" ? "en-GB" : "es-ES";
}
