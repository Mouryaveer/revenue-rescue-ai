import { render, screen } from "@testing-library/react";
import { KpiCard } from "@/components/charts/kpi-card";
import { describe, it, expect } from "vitest";

describe("KpiCard", () => {
  it("renders label and value", () => {
    render(<KpiCard label="Revenue at Risk" value="₹4,999" />);
    expect(screen.getByText("Revenue at Risk")).toBeTruthy();
    expect(screen.getByText("₹4,999")).toBeTruthy();
  });

  it("renders sub-text when provided", () => {
    render(<KpiCard label="Recovered" value="₹1,000" sub="Verified by simulator" />);
    expect(screen.getByText("Verified by simulator")).toBeTruthy();
  });
});
