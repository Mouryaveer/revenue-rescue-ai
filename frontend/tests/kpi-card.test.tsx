import { render } from "@testing-library/react";
import { KpiCard } from "@/components/charts/kpi-card";
import { describe, it, expect } from "vitest";

describe("KpiCard", () => {
  it("renders label and value", () => {
    const { getByText } = render(<KpiCard label="Revenue at Risk" value="₹4,999" />);
    expect(getByText("Revenue at Risk")).toBeTruthy();
    expect(getByText("₹4,999")).toBeTruthy();
  });

  it("renders sub-text when provided", () => {
    const { getByText } = render(<KpiCard label="Recovered" value="₹1,000" sub="Verified by simulator" />);
    expect(getByText("Verified by simulator")).toBeTruthy();
  });
});
