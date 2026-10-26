import { useEffect, useState } from "react";
import { Link } from "wouter";
import { ArrowLeft, CheckCircle2, CreditCard, RefreshCw, Shield, Sparkles } from "lucide-react";
import { PageFrame, SectionHeading } from "@/components/SiteShell";

type Order = {
  order_id: string;
  amount_paise: number;
  currency: string;
  key_id: string;
  case_id: string;
  provider: string;
};

type RazorpaySuccess = {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
};

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => { open: () => void };
  }
}

const API = "/api/v1";

async function loadCheckoutScript(): Promise<void> {
  if (window.Razorpay) return;
  await new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Razorpay Checkout could not be loaded"));
    document.head.appendChild(script);
  });
}

export default function CheckoutPage() {
  const [caseInput, setCaseInput] = useState("");
  const urlCaseId = new URLSearchParams(window.location.search).get("case_id") || "";
  const [caseId, setCaseId] = useState(urlCaseId);
  const [order, setOrder] = useState<Order | null>(null);
  const [state, setState] = useState("READY");
  const [message, setMessage] = useState("Enter a recovery case ID or click 'Generate Active Case' below.");
  const [creatingCase, setCreatingCase] = useState(false);

  useEffect(() => {
    if (urlCaseId) {
      setCaseId(urlCaseId);
      setCaseInput(urlCaseId);
      setMessage("Case ID loaded. Click 'Open Razorpay Checkout' to create order.");
    }
  }, [urlCaseId]);

  async function handleGenerateCase() {
    setCreatingCase(true);
    setMessage("Generating a new active payment failure case...");
    try {
      const uniqueSuffix = Date.now().toString(36) + Math.random().toString(36).substring(2, 5);
      const res = await fetch(`${API}/events/payment-failed`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          idempotency_key: `evt_chk_${uniqueSuffix}`,
          customer_id: `cust_${uniqueSuffix}`,
          amount_paise: 49900,
          currency: "INR",
          failure_reason: "INSUFFICIENT_FUNDS",
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Case generation failed");
      const newCaseId = data.recovery_case_id;
      setCaseId(newCaseId);
      setCaseInput(newCaseId);
      setState("READY");
      setMessage(`Generated active case (${newCaseId.substring(0, 8)}…). Ready to open Razorpay Checkout!`);
    } catch (err: any) {
      setState("ERROR");
      setMessage(err.message || "Failed to generate test case");
    } finally {
      setCreatingCase(false);
    }
  }

  async function startCheckout() {
    const activeCaseId = (caseId || caseInput).trim();
    if (!activeCaseId) {
      setState("ERROR");
      setMessage("A case ID is required. Please click 'Generate Active Case' or paste an existing ID.");
      return;
    }
    setState("CREATING_ORDER");
    setMessage("Contacting backend and Razorpay Test API to create order...");
    try {
      const response = await fetch(`${API}/payments/orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ case_id: activeCaseId }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Order creation failed");
      }
      setOrder(data);
      await loadCheckoutScript();
      if (!window.Razorpay) throw new Error("Razorpay Checkout script could not be loaded");
      setState("CHECKOUT_OPEN");
      setMessage("Razorpay Checkout modal is now open. Complete the test payment or dismiss.");

      new window.Razorpay({
        key: data.key_id,
        amount: data.amount_paise,
        currency: data.currency,
        name: "RevenueRescue AI",
        description: "Test Mode Recovery Checkout",
        order_id: data.order_id,
        prefill: {
          name: "Test Customer",
          email: "customer@example.com",
          contact: "9999999999",
        },
        theme: {
          color: "#2563eb",
        },
        handler: async (success: RazorpaySuccess) => {
          setState("VERIFYING");
          setMessage("Browser received payment ID. Server is verifying HMAC signature & fetching captured payment from Razorpay...");
          try {
            const verify = await fetch(`${API}/payments/verify`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ ...success, case_id: activeCaseId }),
            });
            const result = await verify.json();
            if (!verify.ok) throw new Error(result.detail || "Payment verification failed");
            setState("VERIFIED");
            setMessage("🎉 Success! Server verified HMAC & provider captured state. Case marked RECOVERED in audit ledger!");
          } catch (vErr: any) {
            setState("ERROR");
            setMessage(vErr.message || "Server verification failed");
          }
        },
        modal: {
          ondismiss: () => {
            setState("DISMISSED");
            setMessage("Checkout modal was closed without completing payment.");
          },
        },
      }).open();
    } catch (error: any) {
      setState("ERROR");
      setMessage(error.message || "Checkout could not be started");
    }
  }

  return (
    <PageFrame>
      <main style={{ background: "#f8fafc", minHeight: "90vh", padding: "40px 0 80px" }}>
        <div className="container" style={{ maxWidth: 760 }}>
          <div style={{ marginBottom: 20 }}>
            <Link href="/dashboard" style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13, color: "#64748b", textDecoration: "none", fontWeight: 600, marginBottom: 12 }}>
              <ArrowLeft size={14} /> Back to Recovery Console
            </Link>
            <span style={{ display: "inline-block", fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 20, background: "rgba(37,99,235,0.1)", color: "#2563eb", border: "1px solid rgba(37,99,235,0.2)" }}>
              Razorpay Test Mode Integration
            </span>
            <h1 style={{ fontSize: 28, fontWeight: 800, margin: "8px 0 6px", color: "#0f172a" }}>
              Case-Bound Checkout Workflow
            </h1>
            <p style={{ margin: 0, color: "#64748b", fontSize: 14 }}>
              Zero real money. Orders are created with Razorpay Test Mode keys. Outcomes are authoritative — verified via HMAC SHA-256 and Razorpay API.
            </p>
          </div>

          <div style={{ background: "#ffffff", borderRadius: 12, border: "1px solid #e2e8f0", padding: 28, boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
            {/* Quick Action: Generate active case */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", background: "#f0f9ff", borderRadius: 8, border: "1px solid #bae6fd", marginBottom: 20 }}>
              <div>
                <span style={{ fontSize: 12, fontWeight: 700, color: "#0369a1", display: "block" }}>Need an active test case?</span>
                <span style={{ fontSize: 12, color: "#0284c7" }}>Generate a fresh ₹499 failed payment case ready for checkout.</span>
              </div>
              <button
                onClick={handleGenerateCase}
                disabled={creatingCase}
                style={{
                  display: "flex", alignItems: "center", gap: 6, padding: "8px 14px",
                  background: "#0284c7", color: "#fff", border: "none", borderRadius: 6,
                  fontSize: 12, fontWeight: 700, cursor: "pointer"
                }}
              >
                {creatingCase ? <RefreshCw size={14} className="animate-spin" /> : <Sparkles size={14} />}
                Generate Active Case
              </button>
            </div>

            {/* Case input */}
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "#334155", marginBottom: 6 }}>
                Recovery Case ID
              </label>
              <input
                type="text"
                value={caseInput}
                onChange={(e) => {
                  setCaseInput(e.target.value);
                  setCaseId(e.target.value);
                }}
                placeholder="e.g. 5a0d0713-7aad-494f-b47b-2f4207394e09"
                style={{
                  width: "100%", padding: "10px 14px", fontFamily: "monospace", fontSize: 13,
                  borderRadius: 6, border: "1px solid #cbd5e1", background: "#f8fafc"
                }}
              />
            </div>

            {/* Status Indicator */}
            <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 14 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: "#475569" }}>Status:</span>
              <span style={{
                padding: "3px 10px", borderRadius: 20, fontSize: 11, fontFamily: "monospace", fontWeight: 700,
                background: state === "VERIFIED" ? "#dcfce7" : state === "ERROR" ? "#fee2e2" : state === "CHECKOUT_OPEN" ? "#fef3c7" : "#f1f5f9",
                color: state === "VERIFIED" ? "#166534" : state === "ERROR" ? "#991b1b" : state === "CHECKOUT_OPEN" ? "#92400e" : "#1e293b",
              }}>
                {state}
              </span>
            </div>

            {order && (
              <div style={{ padding: 14, background: "#f8fafc", borderRadius: 8, border: "1px solid #e2e8f0", marginBottom: 16, fontSize: 13 }}>
                <p style={{ margin: "0 0 6px" }}><strong>Razorpay Order ID:</strong> <code>{order.order_id}</code></p>
                <p style={{ margin: "0 0 6px" }}><strong>Key ID:</strong> <code>{order.key_id}</code></p>
                <p style={{ margin: 0 }}><strong>Amount:</strong> ₹{(order.amount_paise / 100).toFixed(2)} {order.currency}</p>
              </div>
            )}

            <div style={{
              padding: "12px 14px", borderRadius: 8, fontSize: 13, marginBottom: 20,
              background: state === "VERIFIED" ? "#f0fdf4" : state === "ERROR" ? "#fef2f2" : "#f8fafc",
              border: state === "VERIFIED" ? "1px solid #bbf7d0" : state === "ERROR" ? "1px solid #fecaca" : "1px solid #e2e8f0",
              color: state === "VERIFIED" ? "#166534" : state === "ERROR" ? "#991b1b" : "#475569"
            }}>
              {message}
            </div>

            <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
              <button
                className="button-link button-primary"
                onClick={startCheckout}
                disabled={state === "CREATING_ORDER" || state === "VERIFYING"}
                style={{
                  display: "inline-flex", alignItems: "center", gap: 8, padding: "12px 20px",
                  background: "#2563eb", color: "#fff", border: "none", borderRadius: 6,
                  fontSize: 14, fontWeight: 700, cursor: "pointer"
                }}
              >
                {state === "CREATING_ORDER" ? (
                  <>
                    <RefreshCw size={16} className="animate-spin" /> Creating Order…
                  </>
                ) : state === "VERIFYING" ? (
                  <>
                    <RefreshCw size={16} className="animate-spin" /> Verifying with Razorpay…
                  </>
                ) : (
                  <>
                    <CreditCard size={16} /> Open Razorpay Checkout
                  </>
                )}
              </button>
            </div>

            <div style={{ marginTop: 24, paddingTop: 18, borderTop: "1px solid #f1f5f9", display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#94a3b8" }}>
              <Shield size={14} color="#16a34a" />
              <span>Safe Environment: Connected to Razorpay Test API. No actual cards or funds will be charged.</span>
            </div>
          </div>
        </div>
      </main>
    </PageFrame>
  );
}
