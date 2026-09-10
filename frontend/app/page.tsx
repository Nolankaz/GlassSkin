import ProfileManager from "@/components/ProfileManager";

export default function Home() {
  return (
    <main className="app-shell">
      <section className="hero">
        <span className="eyebrow">AI skin profile system</span>
        <h1>GlassSkinAI</h1>

        <p className="lead">
          Build a structured skin profile and research treatment options with
          a calm, clinically minded AI workflow.
        </p>
      </section>

      <ProfileManager />
    </main>
  );
}
