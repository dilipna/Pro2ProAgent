import { EvidencePreview } from "@/components/evidence-preview";
import { Footer } from "@/components/footer";
import { Hero } from "@/components/hero";
import { Method } from "@/components/method";
import { Nav } from "@/components/nav";
import { PipelineStats } from "@/components/pipeline-stats";
import { PrototypePreview } from "@/components/prototype-preview";
import { RecordedSearch } from "@/components/recorded-search";
import { backendConnected } from "@/lib/backend-mode";
import { Search } from "@/components/search";
import { Showcase } from "@/components/showcase";

export const dynamic = "force-dynamic";

export default function Home() {
  return (
    <>
      <Nav />
      <main className="flex-1">
        <Hero />
        <PrototypePreview />
        <EvidencePreview />
        <Showcase />
        {backendConnected() ? <Search /> : <RecordedSearch />}
        <Method />
        <PipelineStats />
      </main>
      <Footer />
    </>
  );
}
