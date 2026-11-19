import { Link, useOutletContext } from "react-router-dom";
import { Button } from "../components/ui/button";

export function HomePage() {
  const { workspaceSearch } = useOutletContext<{ workspaceSearch: string }>();
  return <section className="editorial-home workspace-container hero-enter" aria-labelledby="home-title">
    <h1 id="home-title" className="hero-title">Clarity from<br className="hidden sm:block" /> conflicting data.</h1>
    <p className="hero-description">Compare Flights reports from different sources, find disagreements, and review possible corrections—with AI assistance when needed.</p>
    <Button asChild variant="accent" className="hero-action"><Link to={{ pathname: "/datasets", search: workspaceSearch }}>Open workspace</Link></Button>
  </section>;
}
