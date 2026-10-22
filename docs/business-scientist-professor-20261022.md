# Virtual Chief Economist and Business Scientist

## Purpose

The business-scientist-professor role coordinates evidence-led management for
Zomorod Melal and MojPlayWin. It covers strategy, customer discovery, marketing
and sales, product design, production, finance, technology, people, risk, and
organizational learning. It is an operational decision-support role, not a
claim that a human professor has been hired or that external systems are already
connected.

## Run one management cycle

    python manage.py business_scientist_cycle

Add --record to save a sanitized audit receipt. The command is read-only
except for that explicit receipt. It uses the connected Django database and
labels factory, production-site, market, and settled-cash data as unknown when
no verified adapter supplies them.

The cycle selects the highest-priority visible constraint and turns it into a
falsifiable experiment with a primary measure, baseline requirement, decision
rule, and guardrail. The resulting action is a plan, not a false claim that a
worker executed it.

## Scientific management method

1. Observe timestamped source data and record missing sensors as unknown.
2. Rank the constraint by its effect on customer outcomes and contribution.
3. State one hypothesis that could be disproved.
4. Set a dated baseline and a single primary measure before acting.
5. Limit the intervention by scope, risk, budget, and rollback.
6. Compare the measured result with baseline and inspect guardrails.
7. Retain, repair, or roll back; then choose the next constraint.

The plan contains portfolio gates for validated customer problems, willingness
to pay, reliable delivery, positive unit economics, repeatable acquisition, and
controlled expansion. Products do not advance based on draft counts, CI status,
simulated orders, or internal approval alone.

## Authority boundary

The role may analyze records and propose or perform only already-authorized,
reversible internal diagnostics. Owner approval and appropriate specialist
review remain required for spending, payments, contracts, use of personal data,
production releases, external publication, irreversible changes, and legal or
regulated decisions. It must never simulate owner signatures, human expert
approval, customer acceptance, or settled funds.

## Current integration boundary

This role does not establish continuous operation. Before connecting it to the
VPS factory, either production site, or payment rails, build read-only adapters
with source identity, timestamps, integrity checks, and staleness limits. Shadow
run and reconcile their observations first. Only then should existing
idempotent task capabilities be allowed to perform low-risk interventions,
with preconditions, postconditions, audit receipts, quotas, and tested rollback.
