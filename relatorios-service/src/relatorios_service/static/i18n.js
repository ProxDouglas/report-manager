import { english } from "./translations.js?v=2";

export const Language = Object.freeze({ ENGLISH: "en", PORTUGUESE: "pt-BR" });

class Internationalization {
  constructor() {
    this.language = Language.ENGLISH;
    try {
      const saved = localStorage.getItem("language");
      if (Object.values(Language).includes(saved)) this.language = saved;
    } catch {
      // Storage may be unavailable; keep the default for this session.
    }
    this.bindings = [];
    const walker = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      const source = node.textContent.replace(/\s+/g, " ").trim();
      if (Object.hasOwn(english, source)) this.bindings.push({ node, source });
    }
    for (const node of document.querySelectorAll("[aria-label], [placeholder], meta[name='description']")) {
      for (const attribute of ["aria-label", "placeholder", "content"]) {
        const source = node.getAttribute(attribute);
        if (source && Object.hasOwn(english, source)) this.bindings.push({ node, attribute, source });
      }
    }
  }

  translate(source) {
    if (this.language === Language.ENGLISH) return english[source] || source;
    return source;
  }

  setLanguage(language) {
    if (!Object.values(Language).includes(language)) return;
    this.language = language;
    try {
      localStorage.setItem("language", language);
    } catch {
      // The selector still works without persistent storage.
    }
    this.apply();
  }

  apply() {
    document.documentElement.lang = this.language;
    document.getElementById("language").value = this.language;
    for (const { node, attribute, source } of this.bindings) {
      const value = this.translate(source);
      if (attribute) node.setAttribute(attribute, value);
      else node.textContent = ` ${value} `;
    }
  }
}

export const i18n = new Internationalization();

export function t(source, ...values) {
  if (typeof source === "string") return i18n.translate(source);
  const key = source.reduce((text, part, index) => {
    if (index === 0) return part;
    return `${text}\${${index - 1}}${part}`;
  }, "");
  return i18n.translate(key).replace(/\$\{(\d+)\}/g, (_, index) => String(values[Number(index)]));
}
