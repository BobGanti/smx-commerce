# smx-commerce Support AI Architecture

This document explains the internal support AI architecture used by `smx-commerce`.

The host project does not implement support agents. The host project provides `ai_profile`, and `smx-commerce` uses that profile to build its own provider adapter, agents, orchestration, safety checks, token-usage tracking, and admin-review workflow.

---

## 1. Responsibility boundary

The host project owns the LLM access profiles.

In production SyntaxMatrix, AI profiles should normally come from configured agency/provider records stored in the SyntaxMatrix database. The host reads the agency/provider configuration, builds the provider client, places it in a profile dictionary, and passes that profile into the plugin.

In a temporary sandbox, a local `AI_PROFILES` registry can stand in for the missing SyntaxMatrix host configuration layer.

Example sandbox-style registry:

```python
AI_PROFILES = {
    "google": GEMINI_PROFILE,
    "openai": GPT_PROFILE,
    "anthropic": CLAUDE_PROFILE,
    "xai": GROK_PROFILE,
    "alibaba": QWEN_PROFILE,
    "deepseek": DEEPSEEK_PROFILE,
    "moonshotai": KIMI_PROFILE,
}
```

Each `AI_PROFILES[...]` entry remains a full provider profile. For example:

```python
GROK_PROFILE = {
    "provider": "xai",
    "model": XAI_MODEL,
    "api_key": XAI_API_KEY,
    "client": OpenAI(
        api_key=XAI_API_KEY,
        base_url="https://api.x.ai/v1",
    ),
}
```

`smx-commerce` owns:

- provider adapter creation
- support-agent definitions
- agent prompts and expected schemas
- parallel and sequential orchestration
- deterministic context loading
- deterministic aggregation
- deterministic safety and human-review rules
- token-usage aggregation
- admin review and save workflow

The client project must not create a custom `smx_commerce_ai_client.py` file.

---

## 2. ai_profile contract

`smx-commerce` accepts one public AI argument:

```python
ai_profile=...
```

There is no separate `ai_profiles` argument.

The package supports two shapes.

---

### 2.1 Single-profile shape

This is the simple single-model form:

```python
ai_profile = AI_PROFILES["google"]
```

In this form, all AI support tasks use the same provider profile.

Internally, the package treats this as:

```text
main = AI_PROFILES["google"]
assistant = None
```

---

### 2.2 Labeled main/assistant shape

This is the optimized model-routing form:

```python
ai_profile = {
    "main": AI_PROFILES["xai"],
    "assistant": AI_PROFILES["alibaba"],
}
```

The `main` profile is required.

The `assistant` profile is optional.

The host does not need to pass `"assistant": None`.

This is valid:

```python
ai_profile = {
    "main": AI_PROFILES["xai"],
}
```

If `assistant` is missing, `smx-commerce` automatically uses `main` for all AI tasks.

---

## 3. Main and assistant meaning

The labels are task-routing labels, not provider names.

```text
main       -> primary model for heavier reasoning, planning, composition, verification
assistant  -> optional lighter model for narrower support-analysis tasks
```

For support AI:

```text
assistant, when present:
  commerce_support_issue_classifier
  commerce_support_summary
  commerce_support_missing_information
  commerce_support_escalation_assessor
  commerce_support_priority_assessor

main:
  commerce_support_reply_planner
  commerce_support_reply_composer
  commerce_support_reply_verifier
```

If no assistant profile is provided, all tasks use `main`.

---

## 4. Provider and model naming

Provider means vendor/platform.

Model means the actual model name.

Supported provider values are:

```text
google
openai
anthropic
xai
alibaba
deepseek
moonshotai
```

Correct examples:

```python
{"provider": "xai", "model": "grok-..."}
{"provider": "alibaba", "model": "qwen-..."}
{"provider": "deepseek", "model": "deepseek-..."}
{"provider": "moonshotai", "model": "kimi-..."}
```

Do not use model-family names as providers.

Incorrect examples:

```python
{"provider": "grok"}
{"provider": "qwen"}
{"provider": "kimi"}
```

---

## 5. Supported provider profiles

### 5.1 Google / Gemini

```python
from google import genai

GEMINI_PROFILE = {
    "provider": "google",
    "model": GEMINI_MODEL,
    "api_key": GEMINI_API_KEY,
    "client": genai.Client(api_key=GEMINI_API_KEY),
}
```

### 5.2 OpenAI Responses API

```python
from openai import OpenAI

GPT_PROFILE = {
    "provider": "openai",
    "model": OPENAI_MODEL,
    "api_key": OPENAI_API_KEY,
    "client": OpenAI(api_key=OPENAI_API_KEY),
}
```

### 5.3 Anthropic Messages API

```python
from anthropic import Anthropic

CLAUDE_PROFILE = {
    "provider": "anthropic",
    "model": ANTHROPIC_MODEL,
    "api_key": ANTHROPIC_API_KEY,
    "client": Anthropic(api_key=ANTHROPIC_API_KEY),
}
```

### 5.4 xAI / Grok models

```python
from openai import OpenAI

GROK_PROFILE = {
    "provider": "xai",
    "model": XAI_MODEL,
    "api_key": XAI_API_KEY,
    "client": OpenAI(
        api_key=XAI_API_KEY,
        base_url="https://api.x.ai/v1",
    ),
}
```

### 5.5 Alibaba / Qwen models

```python
from openai import OpenAI

QWEN_PROFILE = {
    "provider": "alibaba",
    "model": QWEN_MODEL,
    "api_key": ALIBABA_API_KEY,
    "client": OpenAI(
        api_key=ALIBABA_API_KEY,
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    ),
}
```

### 5.6 DeepSeek models

```python
from openai import OpenAI

DEEPSEEK_PROFILE = {
    "provider": "deepseek",
    "model": DEEPSEEK_MODEL,
    "api_key": DEEPSEEK_API_KEY,
    "client": OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com",
    ),
}
```

### 5.7 Moonshot AI / Kimi models

```python
from openai import OpenAI

KIMI_PROFILE = {
    "provider": "moonshotai",
    "model": KIMI_MODEL,
    "api_key": MOONSHOTAI_API_KEY,
    "client": OpenAI(
        api_key=MOONSHOTAI_API_KEY,
        base_url="https://api.moonshot.ai/v1",
    ),
}
```

---

## 6. Where ai_profile enters the package

The host passes `ai_profile` into the public setup call:

```python
setup_commerce(
    app,
    init_schema=True,
    ai_profile={
        "main": AI_PROFILES["xai"],
        "assistant": AI_PROFILES["alibaba"],
    },
)
```

The package receives this in:

```text
src/smx_commerce/__init__.py
```

The important handoff happens inside `create_commerce_blueprint()`:

```python
commerce_runtime.ai_profile = ai_profile
commerce_runtime.ai_client = ai_client or build_commerce_ai_client_from_profile(ai_profile)
```

That is where the host-provided profile becomes the runtime AI client used by the package.

---

## 7. Where ai_profile is unpacked and routed

The unpacking and provider-adapter creation happens in:

```text
src/smx_commerce/ai/profiles.py
```

Important objects/functions:

```text
build_commerce_ai_client_from_profile(profile)
_is_labeled_ai_profile(profile)
CommerceAIRoutingClient
```

For a labeled profile:

```python
ai_profile = {
    "main": AI_PROFILES["xai"],
    "assistant": AI_PROFILES["alibaba"],
}
```

the package builds:

```text
main client       -> built from AI_PROFILES["xai"]
assistant client  -> built from AI_PROFILES["alibaba"]
```

Then `CommerceAIRoutingClient` decides which internal support agent uses which client.

---

## 8. Where support admin uses the AI client

The support admin routes live in:

```text
src/smx_commerce/admin/support.py
```

They pull the already-built runtime client:

```python
ai_client = getattr(runtime, "ai_client", None)
```

Then they pass it into:

```text
SupportAnalysisService
```

The support service and agents do not need to know whether the runtime client is a single provider client or a routed client. They call the same `run_agent_task()` method.

---

## 9. Full support reply workflow

A full customer-support reply draft uses 8 internal AI agents.

The workflow is:

```text
customer support message
-> deterministic intake and context loading
-> five parallel analysis agents
-> deterministic triage aggregation
-> reply planner agent
-> reply composer agent
-> reply verifier agent
-> deterministic safety and human-review override
-> admin review/save
```

The orchestrator is not an AI agent. It is deterministic package logic.

---

## 10. Parallel analysis agents

The analysis stage uses five narrow agents that can run in parallel because they do not depend on each other.

When an assistant profile is provided, these agents use the assistant model. If no assistant profile is provided, they use the main model.

### 10.1 Issue Classifier Agent

Agent name:

```text
commerce_support_issue_classifier
```

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

### 10.2 Summary Agent

Agent name:

```text
commerce_support_summary
```

Responsibility:

- summarize the customer issue
- avoid deciding escalation or priority
- avoid composing a response

---

### 10.3 Missing Information Agent

Agent name:

```text
commerce_support_missing_information
```

Responsibility:

- identify missing fields needed to resolve the issue
- examples include order ID, payment reference, account email, product name, or screenshot

---

### 10.4 Escalation Assessor Agent

Agent name:

```text
commerce_support_escalation_assessor
```

Responsibility:

- decide whether the issue should be escalated
- focus on support risk, payment/access sensitivity, refund sensitivity, and unresolved account problems

---

### 10.5 Priority Assessor Agent

Agent name:

```text
commerce_support_priority_assessor
```

Responsibility:

- recommend support priority
- expected priorities: low, normal, high, urgent

---

## 11. Deterministic triage aggregation

After the five analysis agents return, `smx-commerce` aggregates their results deterministically.

The package records:

- issue type
- confidence
- summary
- missing information
- escalation flag
- recommended priority

The LLM does not directly decide database writes. The package aggregates and persists the structured result.

The package also aggregates per-agent and total token usage where provider responses expose usage metadata.

---

## 12. Sequential reply agents

Reply drafting is sequential because each step depends on the previous step.

These agents always use the main profile.

### 12.1 Reply Planner Agent

Agent name:

```text
commerce_support_reply_planner
```

Responsibility:

- decide the reply strategy
- choose facts to include
- identify questions to ask
- identify forbidden claims
- decide whether human review is needed from the planner perspective
- avoid writing the final customer-facing prose

---

### 12.2 Reply Composer Agent

Agent name:

```text
commerce_support_reply_composer
```

Responsibility:

- write the customer-facing draft using the approved plan
- avoid inventing facts
- avoid claiming completed actions such as refunds, cancellations, access restoration, or account changes

---

### 12.3 Reply Verifier Agent

Agent name:

```text
commerce_support_reply_verifier
```

Responsibility:

- verify the drafted reply
- check for hallucinated facts
- check for unsafe completed-action claims
- check for unsupported refund, cancellation, access, or account-change promises
- return concerns and revision flags

The verifier does not replace the deterministic package safety guard.

---

## 13. Deterministic safety and human-review override

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

```text
should_escalate = True
recommended_priority = high
```

then the final reply draft must be stored with:

```text
needs_human_review = True
```

even if the reply verifier says the draft is safe.

---

## 14. Admin review workflow

AI-generated replies are drafts only.

The package does not send the reply automatically.

The admin must review the reply draft inside the support admin panel before saving or sending any response.

When a reviewed reply is saved:

- the reply is added as an admin message
- the pending AI reply draft is cleared
- the saved reply is retained in metadata for audit/history

---

## 15. Routing summary

The current routing policy is deterministic:

```text
assistant if present:
  commerce_support_issue_classifier
  commerce_support_summary
  commerce_support_missing_information
  commerce_support_escalation_assessor
  commerce_support_priority_assessor

main:
  commerce_support_reply_planner
  commerce_support_reply_composer
  commerce_support_reply_verifier
```

If the assistant profile is missing, all tasks use main.

Dynamic agent selection may be added later, but it should remain deterministic package logic. The host project should not decide which internal agents run.
