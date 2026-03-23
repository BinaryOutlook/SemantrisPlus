import { initGameController } from "./controller";
import { resolveGameElements } from "./dom";

const elements = resolveGameElements();
initGameController(elements);
