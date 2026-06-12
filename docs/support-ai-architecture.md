# smx-commerce Support AI Architecture

This document explains the internal support AI architecture used by `smx-commerce`.

The host project does not implement support agents. The host project provides an `ai_profile`, and `smx-commerce` uses that profile to build its own provider adapter, agents, orchestration, safety checks, and admin-review workflow.

---

## 1. Responsibility boundary

The host project owns only the LLM access profile:

    ai_profile = {
        "provider": "google",
        "model": GEMINI_MODEL,
        "api_key": GEMINI_API_KEY,
        "client": genai.Client(api_key=GEMINI_API_KEY),
    }

The host passes the profile into the generated commerce setup function:

    setup_commerce(
        app,
        init_schema=True,
        ai_profile=ai_profile,
    )

`smx-commerce` owns:

- provider adapter creation
- support-agent definitions
- agent prompts and expected schemas
- parallel and sequential orchestration
- deterministic context loading
- deterministic aggregation
- deterministic safety and human-review rules
- admin review and save workflow

The client project must not create a custom `smx_commerce_ai_client.py` file.

---

## 2. Full support reply workflow

A full customer-support reply draft uses 8 internal AI agents.

The workflow is:

    customer support message
    -> deterministic intake and context loading
    -> five parallel analysis agents
    -> deterministic triage aggregation
    -> reply planner agent
    -> reply composer agent
    -> reply verifier agent
    -> deterministic safety and human-review override
    -> admin review/save

The orchestrator is not an AI agent. It is deterministic package logic.

---

## 3. Parallel analysis agents

The analysis stage uses five narrow agents that can run in parallel because they do not depend on each other.

### 3.1 Issue Classifier Agent

Agent name:

    commerce_support_issue_classifier

Responsibility:

- classify the support issue type
- return confidence
- avoid writing any customer-facing reply

Example outputs:

- payment_problem
- account_access_issue
- refund_request
- order_status_question
- general_question

---

### 3.2 Summary Agent

Agent name:

    commerce_support_summary

Responsibility:

- summarize the customer’s issue
- avoid deciding escalation or priority
- avoid composing a response

---

### 3.3 Missing Information Agent

Agent name:

    commerce_support_missing_information

Responsibility:

- identify missing fields needed to resolve the issue
- examples include order ID, payment reference, account email, product name, or screenshot

---

### 3.4 Escalation Assessor Agent

Agent name:

    commerce_support_escalation_assessor

Responsibility:

- decide whether the issue should be escalated
- focus on support risk, payment/access sensitivity, refund sensitivity, and unresolved account problems

---

### 3.5 Priority Assessor Agent

Agent name:

    commerce_support_priority_assessor

Responsibility:

- recommend support priority
- expected priorities: low, normal, high, urgent

---

## 4. Deterministic triage aggregation

After the five analysis agents return, `smx-commerce` aggregates their results deterministically.

The package records:

- issue type
- confidence
- summary
- missing information
- escalation flag
- recommended priority

The LLM does not directly decide database writes. The package aggregates and persists the structured result.

---

## 5. Sequential reply agents

Reply drafting is sequential because each step depends on the previous step.

### 5.1 Reply Planner Agent

Agent name:

    commerce_support_reply_planner

Responsibility:

- decide the reply strategy
- choose facts to include
- identify questions to ask
- identify forbidden claims
- decide whether human review is needed from the planner’s perspective
- avoid writing the final customer-facing prose

---

### 5.2 Reply Composer Agent

Agent name:

    commerce_support_reply_composer

Responsibility:

- write the customer-facing draft using the approved plan
- avoid inventing facts
- avoid claiming completed actions such as refunds, cancellations, access restoration, or account changes

---

### 5.3 Reply Verifier Agent

Agent name:

    commerce_support_reply_verifier

Responsibility:

- verify the drafted reply
- check for hallucinated facts
- check for unsafe completed-action claims
- check for unsupported refund, cancellation, access, or account-change promises
- return concerns and revision flags

The verifier does not replace the deterministic package safety guard.

---

## 6. Deterministic safety and human-review override

After the verifier runs, the package applies deterministic rules.

A draft must require human review if:

- the reply planner requires review
- the verifier requires revision
- the verifier marks the draft unsafe
- triage says the issue should escalate
- triage recommends high or urgent priority
- the thread priority is high or urgent

This rule overrides the LLM.

For example, if triage returns:

    should_escalate = True
    recommended_priority = high

then the final reply draft must be stored with:

    needs_human_review = True

even if the reply verifier says the draft is safe.

---

## 7. Admin review workflow

AI-generated replies are drafts only.

The package does not send the reply automatically.

The admin must review the reply draft inside the support admin panel before saving or sending any response.

When a reviewed reply is saved:

- the reply is added as an admin message
- the pending AI reply draft is cleared
- the saved reply is retained in metadata for audit/history

---

## 8. Provider profile strategy

The first supported provider profile is:

    provider = "google"

The Google profile uses:

    genai.Client(api_key=GEMINI_API_KEY)

The package converts the host-built profile into a `GoogleCommerceAIClient`.

Future provider profiles should follow the same boundary:

- OpenAI Responses API
- Anthropic
- OpenAI-compatible chat-completions providers
  - Alibaba
  - DeepSeek
  - Moonshot/Kimi

The client project should still provide only the profile. The package should own the provider adapter implementation.

---

## 9. Future dynamic routing

The current full support-reply workflow uses all 8 agents.

Future routing can optimize the workflow by selecting agents based on task type and risk level.

Examples:

Simple FAQ-style issue:

    classifier
    summary
    reply planner
    reply composer
    reply verifier

Payment, refund, or access issue:

    all 8 support agents
    deterministic human-review safety check

High-risk account, refund, cancellation, or legal-sensitive issue:

    all 8 support agents
    strict deterministic human-review lock

Dynamic routing should remain deterministic package logic. The host project should not decide which internal agents run.
