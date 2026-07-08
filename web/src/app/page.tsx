import { Footer } from "@/components/footer";
import { Hero } from "@/components/hero";
import { Method } from "@/components/method";
import { Nav } from "@/components/nav";
import { PipelineStats } from "@/components/pipeline-stats";
import { Search } from "@/components/search";
import { Showcase } from "@/components/showcase";

export default function Home() {
  return (
    <>
      <Nav />
      <main className="flex-1">
        <Hero />
        <Showcase />
        <Search />
        <Method />
        <PipelineStats />
      </main>
      <Footer />
    </>
  );
}
