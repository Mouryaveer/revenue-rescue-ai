import { useEffect, useState } from "react";
import { Link } from "wouter";
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

const API = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");

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
  const caseId = new URLSearchParams(window.location.search).get("case_id") || "";
  const [order, setOrder] = useState<Order | null>(null);
  const [state, setState] = useState("READY");
  const [message, setMessage] = useState("Enter a real recovery case ID to begin.");

  useEffect(() => {
    if (!caseId) return;
    setMessage("The order will be created by the backend for this case.");
  }, [caseId]);

  async function startCheckout() {
    if (!caseId) {
      setState("ERROR");
      setMessage("A case_id is required. Open this page as /checkout?case_id=<recovery-case-id>.");
      return;
    }
    setState("CREATING_ORDER");
    try {
      const response = await fetch(`${API}/payments/orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ case_id: caseId }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Order creation failed");
      setOrder(data);
      await loadCheckoutScript();
      if (!window.Razorpay) throw new Error("Razorpay Checkout is unavailable");
      setState("CHECKOUT_OPEN");
      new window.Razorpay({
        key: data.key_id,
        amount: data.amount_paise,
        currency: data.currency,
        name: "RevenueRescue AI",
        description: "Razorpay Test Mode payment",
        order_id: data.order_id,
        handler: async (success: RazorpaySuccess) => {
          setState("VERIFYING");
          setMessage("Checkout returned a callback. The server is verifying signature and provider state.");
          const verify = await fetch(`${API}/payments/verify`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ...success, case_id: caseId }),
          });
          const result = await verify.json();
          if (!verify.ok) throw new Error(result.detail || "Payment verification failed");
          setState(result.status === "recovered" || result.status === "already_verified" ? "VERIFIED" : result.status);
          setMessage(result.message || "Provider verification completed; check the case timeline for evidence.");
        },
        modal: { ondismiss: () => setState("DISMISSED") },
      }).open();
    } catch (error) {
      setState("ERROR");
      setMessage(error instanceof Error ? error.message : "Checkout could not be started");
    }
  }

  return (
    <PageFrame>
      <main>
        <section className="collection-hero">
          <div className="container">
            <span className="eyebrow">Razorpay Test Mode / Checkout</span>
            <SectionHeading title="Complete a real test payment." description="The browser callback is never treated as success. The backend verifies the HMAC and fetches captured state from Razorpay before any case is marked recovered." />
            <div className="metric-card" style={{ maxWidth: 680, marginTop: 28 }}>
              <p><strong>Status:</strong> {state}</p>
              {order && <p><strong>Order:</strong> <code>{order.order_id}</code> · {order.amount_paise} {order.currency}</p>}
              <p>{message}</p>
              <button className="button-link button-primary" onClick={startCheckout} disabled={state === "CREATING_ORDER" || state === "VERIFYING"}>
                {state === "CREATING_ORDER" ? "Creating order…" : "Open Razorpay Checkout"}
              </button>
              <p style={{ marginTop: 18, fontSize: 12 }}>No provider success is displayed until the server confirms the payment.</p>
            </div>
            <Link className="text-link" href="/dashboard/">Return to console ↗</Link>
          </div>
        </section>
      </main>
    </PageFrame>
  );
}
