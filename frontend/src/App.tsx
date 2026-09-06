import { Route, Switch } from "wouter";
import ErrorBoundary from "./components/ErrorBoundary";

import Home           from "./pages/Home";
import RecoveryPage   from "./pages/RecoveryPage";
import SimulationPage from "./pages/SimulationPage";
import PricingPage    from "./pages/PricingPage";
import DashboardPage  from "./pages/DashboardPage";
import NotFound       from "./pages/NotFound";
import CheckoutPage   from "./pages/CheckoutPage";

function Router() {
  return (
    <Switch>
      <Route path="/"            component={Home} />
      <Route path="/recovery/"   component={RecoveryPage} />
      <Route path="/recovery"    component={RecoveryPage} />
      <Route path="/simulation/" component={SimulationPage} />
      <Route path="/simulation"  component={SimulationPage} />
      <Route path="/pricing/"    component={PricingPage} />
      <Route path="/pricing"     component={PricingPage} />
      <Route path="/dashboard/"  component={DashboardPage} />
      <Route path="/dashboard"   component={DashboardPage} />
      <Route path="/checkout/"   component={CheckoutPage} />
      <Route path="/checkout"    component={CheckoutPage} />
      <Route component={NotFound} />
    </Switch>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <Router />
    </ErrorBoundary>
  );
}
