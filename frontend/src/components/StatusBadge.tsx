import { Badge } from "flowbite-react";

const colors: Record<string, string> = {
  complete: "success",
  running: "info",
  queued: "warning",
  failed: "failure",
  canceled: "gray",
  available: "success",
  not_installed: "gray",
  needs_model: "warning",
  needs_library: "warning",
  error: "failure",
};

export function StatusBadge({ value }: { value?: string }) {
  const label = value || "unknown";
  return <Badge color={colors[label] || "purple"}>{label.replaceAll("_", " ")}</Badge>;
}
