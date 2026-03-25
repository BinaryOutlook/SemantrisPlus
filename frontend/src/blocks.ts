import { initBlocksController } from "./blocks_controller";
import { resolveBlocksElements } from "./blocks_dom";

const elements = resolveBlocksElements();
initBlocksController(elements);
