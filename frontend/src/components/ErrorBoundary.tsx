import { AlertTriangle, RotateCcw } from "lucide-react";
import { Component, type ReactNode } from "react";

interface Props  { children: ReactNode }
interface State  { hasError: boolean; error: Error | null }

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", padding: 32, background: "#f4f7ff" }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: "100%", maxWidth: 680, padding: 40, background: "#fff", border: "1px solid #dde5f2" }}>
            <AlertTriangle size={44} color="#ef4444" style={{ marginBottom: 20 }} />
            <h2 style={{ margin: "0 0 18px", font: "700 22px/1 Manrope, sans-serif", letterSpacing: "-.04em", color: "#14213d" }}>
              Something went wrong
            </h2>
            <pre style={{ width: "100%", padding: 16, background: "#f4f7ff", fontSize: 12, color: "#64748b", overflow: "auto", marginBottom: 24, borderRadius: 4, whiteSpace: "pre-wrap" }}>
              {this.state.error?.message}
            </pre>
            <button
              onClick={() => window.location.reload()}
              style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "10px 20px", background: "#1747f5", color: "#fff", borderRadius: 4, fontWeight: 700, fontSize: 13, cursor: "pointer" }}
            >
              <RotateCcw size={15} /> Reload page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
