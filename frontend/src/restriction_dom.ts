import type { GameElements } from "./dom";
import { resolveGameElements } from "./dom";

export interface RestrictionElements extends GameElements {
  activeRuleName: HTMLElement;
  activeRuleDescription: HTMLElement;
  strikeValue: HTMLElement;
  strikeMeter: HTMLElement;
  ruleResultValue: HTMLElement;
}

function requireElement<T extends HTMLElement>(id: string, documentRef: Document): T {
  const element = documentRef.getElementById(id);
  if (!(element instanceof HTMLElement)) {
    throw new Error(`Missing required element: #${id}`);
  }

  return element as T;
}

export function resolveRestrictionElements(documentRef: Document = document): RestrictionElements {
  return {
    ...resolveGameElements(documentRef),
    activeRuleName: requireElement("active-rule-name", documentRef),
    activeRuleDescription: requireElement("active-rule-description", documentRef),
    strikeValue: requireElement("strike-value", documentRef),
    strikeMeter: requireElement("strike-meter", documentRef),
    ruleResultValue: requireElement("rule-result-value", documentRef),
  };
}
