import Workspace from "@/components/review-workspace";

export default async function WorkspacePage({
  searchParams,
}: {
  searchParams: Promise<{ handoff?: string | string[] }>;
}) {
  const params = await searchParams;
  const handoff = typeof params.handoff === "string" && /^[a-f0-9-]{36}$/.test(params.handoff)
    ? params.handoff : null;
  return <Workspace handoff={handoff} />;
}
