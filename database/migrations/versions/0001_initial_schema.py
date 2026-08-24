"""Initial schema — all tables

Revision ID: 0001
Revises:
Create Date: 2026-08-23

"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="OPERATOR"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── simulation_runs ────────────────────────────────────────────────────
    op.create_table(
        "simulation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("simulation_id", sa.String(128), nullable=False, unique=True),
        sa.Column("label", sa.String(255), nullable=False, server_default="Simulation Run"),
        sa.Column("random_seed", sa.Integer, nullable=False),
        sa.Column("policy_version", sa.String(50), nullable=False),
        sa.Column("agent_version", sa.String(50), nullable=False),
        sa.Column("dataset_version", sa.String(50), nullable=False),
        sa.Column("num_customers", sa.Integer, nullable=False),
        sa.Column("num_events", sa.Integer, nullable=False),
        sa.Column("failure_rate", sa.Float, nullable=False),
        sa.Column("is_baseline", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("config", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("progress_pct", sa.Float, nullable=False, server_default="0"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("results", postgresql.JSONB, nullable=True),
        sa.Column("revenue_at_risk_paise", sa.Integer, nullable=False, server_default="0"),
        sa.Column("revenue_recovered_paise", sa.Integer, nullable=False, server_default="0"),
        sa.Column("recovery_rate_pct", sa.Float, nullable=False, server_default="0"),
        sa.Column("total_cases", sa.Integer, nullable=False, server_default="0"),
        sa.Column("recovered_cases", sa.Integer, nullable=False, server_default="0"),
        sa.Column("escalated_cases", sa.Integer, nullable=False, server_default="0"),
        sa.Column("policy_violations", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_simulation_runs_simulation_id", "simulation_runs", ["simulation_id"])

    # ── policies ───────────────────────────────────────────────────────────
    op.create_table(
        "policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("policy_id", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("config", postgresql.JSONB, nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_policies_policy_id", "policies", ["policy_id"])

    # ── customers ─────────────────────────────────────────────────────────
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("email_display", sa.String(255), nullable=False),
        sa.Column("phone_display", sa.String(50), nullable=True),
        sa.Column("segment", sa.String(50), nullable=False, server_default="standard"),
        sa.Column("country", sa.String(10), nullable=False, server_default="IN"),
        sa.Column("opted_out_communication", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("opted_out_email", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("opted_out_sms", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_suspended", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_synthetic", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("total_transactions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("successful_transactions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed_transactions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("lifetime_value_paise", sa.Integer, nullable=False, server_default="0"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_customers_email_hash", "customers", ["email_hash"])

    # ── payment_methods ────────────────────────────────────────────────────
    op.create_table(
        "payment_methods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("method_type", sa.String(50), nullable=False),
        sa.Column("display_label", sa.String(100), nullable=False),
        sa.Column("is_expired", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_valid", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("expiry_month", sa.Integer, nullable=True),
        sa.Column("expiry_year", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payment_methods_customer_id", "payment_methods", ["customer_id"])

    # ── subscriptions ──────────────────────────────────────────────────────
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("payment_method_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payment_methods.id"), nullable=True),
        sa.Column("plan_name", sa.String(255), nullable=False),
        sa.Column("plan_interval", sa.String(50), nullable=False),
        sa.Column("amount_paise", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(30), nullable=False, server_default="ACTIVE"),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("grace_period_days", sa.Integer, nullable=False, server_default="7"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_subscriptions_customer_id", "subscriptions", ["customer_id"])

    # ── checkout_sessions (before transactions — transactions FK to it) ────
    op.create_table(
        "checkout_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("payment_method_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payment_methods.id"), nullable=True),
        sa.Column("session_token", sa.String(128), nullable=False, unique=True),
        sa.Column("amount_paise", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(50), nullable=False, server_default="STARTED"),
        sa.Column("abandoned_at", sa.String(50), nullable=True),
        sa.Column("recovery_message_sent_at", sa.String(50), nullable=True),
        sa.Column("recovery_message_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("resumed_at", sa.String(50), nullable=True),
        sa.Column("completed_at", sa.String(50), nullable=True),
        # recovery_case_id added via ALTER after recovery_cases table created
        sa.Column("is_synthetic", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_checkout_sessions_customer_id", "checkout_sessions", ["customer_id"])
    op.create_index("ix_checkout_sessions_session_token", "checkout_sessions", ["session_token"])

    # ── transactions ───────────────────────────────────────────────────────
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("payment_method_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payment_methods.id"), nullable=True),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscriptions.id"), nullable=True),
        sa.Column("checkout_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("checkout_sessions.id"), nullable=True),
        sa.Column("simulation_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("simulation_runs.id"), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False, unique=True),
        sa.Column("amount_paise", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("failure_reason", sa.String(50), nullable=True),
        sa.Column("failure_message", sa.Text, nullable=True),
        sa.Column("gateway_reference", sa.String(128), nullable=True),
        sa.Column("is_synthetic", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_transactions_customer_id", "transactions", ["customer_id"])
    op.create_index("ix_transactions_idempotency_key", "transactions", ["idempotency_key"])

    # ── recovery_cases ─────────────────────────────────────────────────────
    op.create_table(
        "recovery_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("transactions.id"), nullable=True),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscriptions.id"), nullable=True),
        sa.Column("checkout_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("checkout_sessions.id"), nullable=True),
        sa.Column("simulation_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("simulation_runs.id"), nullable=True),
        sa.Column("scenario", sa.String(50), nullable=False),
        sa.Column("failure_reason", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="DETECTED"),
        sa.Column("amount_at_risk_paise", sa.Integer, nullable=False),
        sa.Column("amount_recovered_paise", sa.Integer, nullable=False, server_default="0"),
        sa.Column("currency", sa.String(10), nullable=False, server_default="INR"),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("communication_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("recovery_score", sa.Float, nullable=True),
        sa.Column("diagnosis", postgresql.JSONB, nullable=True),
        sa.Column("strategy", postgresql.JSONB, nullable=True),
        sa.Column("policy_decision", sa.String(30), nullable=True),
        sa.Column("is_recovered", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_stopped", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("escalation_reason", sa.Text, nullable=True),
        sa.Column("source_event_key", sa.String(128), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_recovery_cases_customer_id", "recovery_cases", ["customer_id"])
    op.create_index("ix_recovery_cases_source_event_key", "recovery_cases", ["source_event_key"])

    # Back-fill FK from checkout_sessions → recovery_cases
    op.add_column("checkout_sessions",
        sa.Column("recovery_case_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("recovery_cases.id"), nullable=True))

    # ── payment_failures ───────────────────────────────────────────────────
    op.create_table(
        "payment_failures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("failure_reason", sa.String(50), nullable=False),
        sa.Column("failure_message", sa.Text, nullable=True),
        sa.Column("gateway_code", sa.String(100), nullable=True),
        sa.Column("amount_paise", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="INR"),
        sa.Column("is_processed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("recovery_case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recovery_cases.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payment_failures_transaction_id", "payment_failures", ["transaction_id"])
    op.create_index("ix_payment_failures_customer_id", "payment_failures", ["customer_id"])

    # ── agent_runs ─────────────────────────────────────────────────────────
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("recovery_case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recovery_cases.id"), nullable=False),
        sa.Column("llm_provider", sa.String(50), nullable=False),
        sa.Column("run_status", sa.String(30), nullable=False, server_default="RUNNING"),
        sa.Column("node_trace", postgresql.JSONB, nullable=True),
        sa.Column("llm_input", postgresql.JSONB, nullable=True),
        sa.Column("llm_output", postgresql.JSONB, nullable=True),
        sa.Column("llm_latency_ms", sa.Integer, nullable=True),
        sa.Column("total_latency_ms", sa.Integer, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agent_runs_recovery_case_id", "agent_runs", ["recovery_case_id"])

    # ── agent_decisions ────────────────────────────────────────────────────
    op.create_table(
        "agent_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("recovery_case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recovery_cases.id"), nullable=False),
        sa.Column("node", sa.String(100), nullable=False),
        sa.Column("decision_type", sa.String(100), nullable=False),
        sa.Column("input_data", postgresql.JSONB, nullable=True),
        sa.Column("output_data", postgresql.JSONB, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agent_decisions_agent_run_id", "agent_decisions", ["agent_run_id"])

    # ── recovery_actions ───────────────────────────────────────────────────
    op.create_table(
        "recovery_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("recovery_case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recovery_cases.id"), nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id"), nullable=True),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("strategy_code", sa.String(50), nullable=False),
        sa.Column("policy_decision", sa.String(30), nullable=False),
        sa.Column("policy_version", sa.Integer, nullable=False),
        sa.Column("was_executed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("execution_result", sa.String(50), nullable=True),
        sa.Column("result_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount_recovered_paise", sa.Integer, nullable=False, server_default="0"),
        sa.Column("action_idempotency_key", sa.String(128), nullable=False, unique=True),
        sa.Column("input_payload", postgresql.JSONB, nullable=True),
        sa.Column("output_payload", postgresql.JSONB, nullable=True),
        sa.Column("denial_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_recovery_actions_recovery_case_id", "recovery_actions", ["recovery_case_id"])
    op.create_index("ix_recovery_actions_action_idempotency_key", "recovery_actions", ["action_idempotency_key"])

    # ── escalations ────────────────────────────────────────────────────────
    op.create_table(
        "escalations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("recovery_case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recovery_cases.id"), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("escalation_type", sa.String(100), nullable=False),
        sa.Column("resolved", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("resolved_by", sa.String(255), nullable=True),
        sa.Column("resolution_notes", sa.Text, nullable=True),
        sa.Column("context_snapshot", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_escalations_recovery_case_id", "escalations", ["recovery_case_id"])

    # ── audit_events ───────────────────────────────────────────────────────
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("recovery_case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recovery_cases.id"), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=True),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount_paise", sa.Integer, nullable=True),
        sa.Column("currency", sa.String(10), nullable=False, server_default="INR"),
        sa.Column("policy_id", sa.String(128), nullable=True),
        sa.Column("policy_version", sa.Integer, nullable=True),
        sa.Column("result", sa.String(50), nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("correlation_id", sa.String(128), nullable=True),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_events_recovery_case_id", "audit_events", ["recovery_case_id"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_correlation_id", "audit_events", ["correlation_id"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("escalations")
    op.drop_table("recovery_actions")
    op.drop_table("agent_decisions")
    op.drop_table("agent_runs")
    op.drop_table("payment_failures")
    op.drop_column("checkout_sessions", "recovery_case_id")
    op.drop_table("recovery_cases")
    op.drop_table("transactions")
    op.drop_table("checkout_sessions")
    op.drop_table("subscriptions")
    op.drop_table("payment_methods")
    op.drop_table("customers")
    op.drop_table("policies")
    op.drop_table("simulation_runs")
    op.drop_table("users")
