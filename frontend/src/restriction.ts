import { initRestrictionController } from "./restriction_controller";
import { resolveRestrictionElements } from "./restriction_dom";

const elements = resolveRestrictionElements();
initRestrictionController(elements);
