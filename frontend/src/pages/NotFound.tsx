import { Link } from "wouter";
import { PageFrame, ButtonLink } from "@/components/SiteShell";

export default function NotFound() {
  return (
    <PageFrame>
      <section className="collection-hero" style={{ minHeight: "60vh", display: "flex", alignItems: "center" }}>
        <div className="container">
          <span className="eyebrow">404</span>
          <h1>This route doesn't <em>exist.</em></h1>
          <p>The page you're looking for hasn't been recovered — even the AI can't find it.</p>
          <div className="hero-actions" style={{ marginTop: 28 }}>
            <ButtonLink href="/">Back home</ButtonLink>
            <Link href="/dashboard/" className="text-link">Open console ↗</Link>
          </div>
        </div>
      </section>
    </PageFrame>
  );
}
