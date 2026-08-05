declare module "react-cytoscapejs" {
  import type { ComponentType } from "react";

  type CytoscapeComponentProps = {
    elements: unknown[];
    style?: Record<string, string | number>;
    layout?: Record<string, unknown>;
    stylesheet?: unknown[];
    cy?: (cy: any) => void;
  };

  const CytoscapeComponent: ComponentType<CytoscapeComponentProps>;
  export default CytoscapeComponent;
}
