

## Comprehensive Summary: Azure Policy Governance Plugin & Compliance Prioritizer Agent

---

### 1. What Does the Custom Plugin Do?

The **AzurePolicy Yashure** plugin is a custom API-based plugin deployed in Microsoft Security Copilot that connects to the Azure Resource Manager (ARM) APIs to query, analyze, and act on Azure Policy compliance data within a given Azure subscription. It enables Security Copilot to:

- Retrieve all policy definitions (what rules exist)
- Retrieve all policy assignments (what rules are actively applied)
- Query resource-level compliance states (which specific resources are compliant or non-compliant)
- Summarize compliance at the policy-definition level (which policies are compliant or non-compliant, including those within initiatives)
- Trigger remediation tasks for non-compliant resources
- Force on-demand compliance re-evaluation scans

The plugin is designed to serve as a **tool layer** for the **Azure Policy Compliance Prioritizer Agent**, which orchestrates multi-step analysis workflows on top of the raw data the plugin returns.

---

### 2. API Calls, Endpoints, and Resource Types

The plugin defines **6 operations**, all targeting `https://management.azure.com`:

#### Operation 1: `ListPolicyDefinitions`
| Detail | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/subscriptions/{subscriptionId}/providers/Microsoft.Authorization/policyDefinitions` |
| **api-version** | `2023-04-01` |
| **Resource Type** | `Microsoft.Authorization/policyDefinitions` |
| **Purpose** | Retrieves every policy definition in the subscription — both BuiltIn (Microsoft-authored) and Custom (user-created). Returns human-readable metadata: `displayName`, `description`, and `policyType`. Used by the agent to cross-reference policy definition IDs from other operations with human-readable names, understand the intent behind each policy, and distinguish BuiltIn vs Custom definitions for effect assessment. |
| **Key Response Fields** | `id`, `properties.displayName`, `properties.description`, `properties.policyType` |

#### Operation 2: `ListPolicyAssignments`
| Detail | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/subscriptions/{subscriptionId}/providers/Microsoft.Authorization/policyAssignments` |
| **api-version** | `2023-04-01` |
| **Resource Type** | `Microsoft.Authorization/policyAssignments` |
| **Purpose** | Retrieves all active policy assignments — the link between policy definitions/initiatives and the scopes (subscription, resource groups) they're applied to. Used by the agent to understand which controls are actively enforced and their scope. |
| **Key Response Fields** | `id`, `name`, `properties.scope`, `properties.policyDefinitionId` |

#### Operation 3: `QueryPolicyComplianceStates`
| Detail | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/subscriptions/{subscriptionId}/providers/Microsoft.PolicyInsights/policyStates/latest/queryResults` |
| **api-version** | `2019-10-01` (pinned via `enum`) |
| **Resource Type** | `Microsoft.PolicyInsights/policyStates` |
| **Purpose** | Queries the latest compliance evaluation states at the **individual resource level**. Returns one record per resource per active policy assignment. This is the most granular view — it tells you exactly which resources are compliant, non-compliant, exempt, etc., and against which specific policy. Used by the agent to gather non-compliant resource records with full context (timestamps, resource types, locations, effects, categories). |
| **Key Parameters** | `$filter` (OData filtering by ComplianceState, PolicyDefinitionId, etc.), `$top` (pagination), `$orderby`, `$select` |
| **Key Response Fields** | `timestamp`, `resourceId`, `policyAssignmentId`, `policyAssignmentName`, `policyDefinitionId`, `policyDefinitionName`, `policyDefinitionAction` (effect), `policyDefinitionCategory`, `policySetDefinitionId`, `complianceState`, `resourceType`, `resourceLocation`, `resourceGroup`, `complianceReasonCode`, `managementGroupIds` |
| **Important Distinction** | Returns **resource-level records**, NOT policy-level counts. For policy-level compliance, use `SummarizeCompliance` instead. |

#### Operation 4: `SummarizeCompliance`
| Detail | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/subscriptions/{subscriptionId}/providers/Microsoft.PolicyInsights/policyStates/latest/summarize` |
| **api-version** | `2019-10-01` (pinned via `enum`) |
| **Resource Type** | `Microsoft.PolicyInsights/policyStates` |
| **Purpose** | Returns aggregate compliance counts broken down by policy assignment and then by individual policy definition within each assignment. This matches the Azure Portal's Policy Overview compliance view. For initiatives (policy sets), it enumerates every individual definition within the initiative with its own `nonCompliantResources` count. A definition with `nonCompliantResources: 0` is compliant. Used by the agent to determine which specific policies are compliant vs non-compliant, get per-definition resource counts for prioritization, and understand the effect configured on each definition. |
| **Key Parameters** | `$top` (number of assignment summaries), `$filter` |
| **Key Response Fields** | Nested structure: `value[].results.nonCompliantResources`, `value[].results.nonCompliantPolicies`, `value[].policyAssignments[].policyAssignmentId`, `value[].policyAssignments[].policySetDefinitionId`, `value[].policyAssignments[].policyDefinitions[].policyDefinitionId`, `value[].policyAssignments[].policyDefinitions[].policyDefinitionReferenceId`, `value[].policyAssignments[].policyDefinitions[].effect`, `value[].policyAssignments[].policyDefinitions[].results.nonCompliantResources` |

#### Operation 5: `TriggerRemediation`
| Detail | Value |
|---|---|
| **Method** | `PUT` |
| **Endpoint** | `/subscriptions/{subscriptionId}/providers/Microsoft.PolicyInsights/remediations/{remediationName}` |
| **api-version** | `2021-10-01` |
| **Resource Type** | `Microsoft.PolicyInsights/remediations` |
| **Purpose** | Creates a remediation task to auto-fix non-compliant resources. Only works for policies with `deployIfNotExists` or `modify` effects. Used by the agent to offer remediation when the user explicitly requests it. The agent should suggest remediation but NOT trigger it automatically. |
| **Key Request Fields** | `properties.policyAssignmentId` (required), `properties.resourceDiscoveryMode` (`ExistingNonCompliant` or `ReEvaluateCompliance`) |
| **Known Gap** | Currently missing `policyDefinitionReferenceId` in request body — needed to remediate a specific definition within an initiative. This is a pending single-field addition. |

#### Operation 6: `TriggerPolicyScan`
| Detail | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/subscriptions/{subscriptionId}/providers/Microsoft.PolicyInsights/policyStates/latest/triggerEvaluation` |
| **api-version** | `2019-10-01` |
| **Resource Type** | `Microsoft.PolicyInsights/policyStates` |
| **Purpose** | Forces an on-demand compliance re-evaluation for all resources in the subscription. Returns HTTP 202 Accepted with a `Location` header to track progress. Used when the user wants fresh compliance data before running analysis. |

---

### 3. Critical JSON/YAML Parsing Details for the Plugin to Work

These are the hard-won lessons discovered through extensive trial-and-error testing in Security Copilot:

#### 3.1 `subscriptionId` Parameter Descriptions
- Every `subscriptionId` path parameter MUST include a description that helps Security Copilot's LLM extract the GUID from the user's natural language prompt
- Without this, Security Copilot sends the literal `{subscriptionId}` template string (URL-encoded as `%7BsubscriptionId%7D`) instead of the actual subscription ID, resulting in a 400 Bad Request
- The working format uses an example GUID: `"This is a GUID such as a1b2c3d4-e5f6-7890-abcd-ef1234567890. Extract this value from the user's query."`
- The `ListPolicyDefinitions` operation works with just `"The Azure Subscription ID."` as a short description — but the longer format works across all operations

#### 3.2 `requestBody` on POST Operations
- The `QueryPolicyComplianceStates` and `SummarizeCompliance` operations are POST endpoints that require `requestBody` declared in the OpenAPI spec, even though the body is empty
- Without `requestBody: required: false` with an empty `application/json` schema, Security Copilot fails to construct the POST call correctly, resulting in "resource type not found" errors
- This is because Security Copilot's API plugin engine needs the `requestBody` declaration to know it should send a POST with `Content-Type: application/json`

#### 3.3 `api-version` Pinning with `enum`
- The `QueryPolicyComplianceStates` and `SummarizeCompliance` operations use `api-version: 2019-10-01`
- This MUST be enforced using `enum: ["2019-10-01"]` combined with `default: "2019-10-01"` — without `enum`, Security Copilot may substitute a different API version, causing errors
- Other operations (`ListPolicyDefinitions`, `ListPolicyAssignments`) use `2023-04-01` with just `default` (no `enum`) and work fine

#### 3.4 OData `$filter` Field Names Must Use PascalCase
- When filtering on `QueryPolicyComplianceStates`, field names MUST use PascalCase: `ComplianceState`, `PolicyDefinitionId`, `ResourceType` — NOT `complianceState`, `policyDefinitionId`, `resourceType`
- This is called out in the `$filter` parameter description to guide the LLM
- Using the wrong casing returns empty results or errors

#### 3.5 Response Schema Depth Sensitivity
- Security Copilot's OpenAPI parser has limits on schema nesting depth
- The `SummarizeCompliance` response has the deepest nesting: `value[].policyAssignments[].policyDefinitions[].results.nonCompliantResources` (5 levels deep) — this works
- However, adding additional deeply nested objects (like `metadata.category` inside `policyRule.then.effect` inside `ListPolicyDefinitions`) was found to cause plugin loading failures in earlier v2 attempts
- Keep response schemas as flat as possible; only nest when the API response structure requires it

#### 3.6 Operation Description Length and Complexity
- Security Copilot uses `operationId`, `summary`, and `description` for **skill routing** — deciding which operation to call for a given user prompt
- Descriptions can be multi-paragraph with routing hints (e.g., "When a user asks to 'list compliant policies', this is the correct operation to use") — this was proven to work in the `SummarizeCompliance` operation
- However, descriptions that are too instructional (GPT-like reasoning prompts) belong in the agent instructions, not in the API spec

#### 3.7 Plugin Manifest Wrapper (`AzurePolicyManagerPluginManifest.yaml`)
- Uses Security Copilot's YAML manifest format with `Descriptor` + `SkillGroups`
- Authentication: `AADDelegated` with `EntraScopes: https://management.azure.com/user_impersonation` — uses the logged-in user's permissions
- `DescriptionForModel` field is critical for plugin selection — tells the LLM when to choose this plugin
- `OpenApiSpecUrl` points to a GitHub Gist hosting the OpenAPI spec
- The `Icon` field is **NOT supported** in Security Copilot custom plugin manifests — including it causes upload failures
- When updating the OpenAPI spec URL, you MUST delete and re-add the plugin — Security Copilot caches the spec and doesn't always re-fetch on URL changes

#### 3.8 `@odata` Property Names
- Response properties with `@` characters (like `@odata.context`, `@odata.count`, `@odata.nextLink`, `@odata.id`) must be quoted in the YAML: `'@odata.context'`
- `@odata.nextLink` indicates pagination — more results are available beyond the current response

---

### 4. What the Agent Is Supposed to Do

The **Azure Policy Compliance Prioritizer** agent is a Security Copilot custom agent that analyzes non-compliant Azure policies and delivers a prioritized, actionable compliance report. Its core responsibilities:

#### 4.1 Prioritize Non-Compliant Policies by Security Impact
Not all non-compliant policies are equally urgent. The agent assigns each non-compliant policy to a 4-tier priority framework based on the **policy's stated intent** (from its displayName and description), NOT based on its current effect (which may be misconfigured):

- **🔴 TIER 1 — CRITICAL:** Policies protecting identity, encryption, access control, key management, secrets, certificates, or privileged access. Policies targeting high-value resources (VMs, SQL databases, Key Vaults, NSGs). Highest `nonCompliantResources` count. Non-compliance older than 7 days.
- **🟠 TIER 2 — HIGH:** Policies related to monitoring, logging, diagnostics, backup, disaster recovery, threat detection. Targeting Storage Accounts, Containers, App Services. Moderate resource counts. Non-compliance older than 3 days.
- **🟡 TIER 3 — MEDIUM:** Policies for cost management, naming conventions, regional restrictions, operational best practices. Non-critical resource types. Low resource counts.
- **🟢 TIER 4 — LOW:** Informational or tagging policies. Very low resource counts (1-2 resources). Non-compliance less than 24 hours old (may self-resolve).

#### 4.2 Assess Whether Policy Effects Are Correctly Configured
For each non-compliant policy, the agent evaluates whether the current effect matches the policy's stated intent and flags misconfigurations:

- A policy that intends to **PREVENT** (keywords: "require", "enforce", "deny", "block") using `audit` instead of `deny` → **Misconfigured**
- A policy that intends to **MONITOR** (keywords: "audit", "log", "detect") using `deny` → **Misconfigured** (unnecessarily blocking deployments)
- A policy that intends to **AUTO-DEPLOY** (keywords: "deploy", "configure", "enable") using `audit` or `deny` instead of `deployIfNotExists`/`modify` → **Misconfigured**
- A policy using `disabled` but actively assigned → **Contradictory**
- Extra attention to Custom policies (policyType = 'Custom') as they're human-created and more error-prone

#### 4.3 Provide Actionable Remediation Steps
For each non-compliant policy:

- Specific remediation actions tailored to the resource type and policy requirement
- Whether auto-remediation is available (`deployIfNotExists`/`modify` effects support it)
- If an effect is misconfigured, the CLI/Portal steps to correct it
- Effort estimate: Quick Fix (< 1 hour), Medium (1-4 hours), Complex (> 4 hours)

#### 4.4 Handle Multiple Policies Across Various Assigned Definitions
The agent must work across:

- Multiple policy assignments (standalone + initiatives)
- Multiple definitions within initiatives (e.g., an initiative with 12 Defender-related definitions)
- Mixed compliance states (some definitions compliant, others not, within the same initiative)

#### 4.5 Present a Structured Compliance Report
Output format:

- Executive summary (total non-compliant, misconfigured effects, quick-fix opportunities, resources affected)
- Per-tier sections with policy detail tables
- Ordered recommended next actions

---

### 5. Full Working: How the Agent Uses Plugin Skills

The agent follows a **7-step workflow**, calling 3 plugin operations to gather data, then applying intelligence across Steps 4-7:

#### STEP 1 → Plugin Skill: `QueryPolicyComplianceStates`

**Call:**
```
POST /subscriptions/{subscriptionId}/providers/Microsoft.PolicyInsights/policyStates/latest/queryResults
?api-version=2019-10-01
&$filter=ComplianceState eq 'NonCompliant'
&$top=5000
```

**What the agent gets:** Every non-compliant resource record across all active policy assignments. Each record contains:
- `policyDefinitionId` + `policyDefinitionName` — which policy is violated
- `policyDefinitionAction` — the current effect (audit, deny, deployIfNotExists, etc.)
- `policyDefinitionCategory` — the policy category (Security, Monitoring, etc.)
- `policySetDefinitionId` — whether it's part of an initiative
- `resourceId`, `resourceType`, `resourceLocation`, `resourceGroup` — which resource is non-compliant
- `timestamp` — when the non-compliance was detected (used for age calculation)
- `complianceReasonCode` — why it's non-compliant

**What the agent does with it:** Builds a list of all unique non-compliant policy definitions, notes the affected resource types and locations, and records timestamps for age-based prioritization.

#### STEP 2 → Plugin Skill: `ListPolicyDefinitions`

**Call:**
```
GET /subscriptions/{subscriptionId}/providers/Microsoft.Authorization/policyDefinitions
?api-version=2023-04-01
```

**What the agent gets:** Every policy definition in the subscription with:
- `displayName` — the human-readable policy name (e.g., "Deploy Microsoft Defender for Key Vaults")
- `description` — full description of what the policy enforces
- `policyType` — `BuiltIn`, `Custom`, or `Static`

**What the agent does with it:** For each unique `policyDefinitionId` from Step 1, the agent finds the matching definition and extracts:
- The `displayName` and `description` — used in Step 4 to determine the policy's **intent** (is it about identity? encryption? monitoring? tagging?)
- The `policyType` — used in Step 5 to flag Custom policies for extra effect scrutiny

#### STEP 3 → Plugin Skill: `SummarizeCompliance`

**Call:**
```
POST /subscriptions/{subscriptionId}/providers/Microsoft.PolicyInsights/policyStates/latest/summarize
?api-version=2019-10-01
&$top=50
```

**What the agent gets:** A nested compliance summary:
```
Subscription Level:
  nonCompliantResources: 5
  nonCompliantPolicies: 5

  Assignment: 895508acc04545058cbfa8ed
    Initiative: f08c57cd-dbd6-49a4-a85e-9ae77ac959b0
    
    Definition: deploydefendersqlservers
      effect: deployIfNotExists
      nonCompliantResources: 0  → COMPLIANT
    
    Definition: deploydefenderai
      effect: deployIfNotExists
      nonCompliantResources: 1  → NON-COMPLIANT
    
    Definition: deploydefenderkeyvaults
      effect: deployIfNotExists
      nonCompliantResources: 0  → COMPLIANT
    
    ... (12 definitions total)
```

**What the agent does with it:** Gets the `nonCompliantResources` count per policy definition — this is the primary metric for prioritization ranking. Definitions with higher counts are ranked higher within their tier.

#### STEP 4 → Agent Intelligence: Prioritize by Policy Intent

**No plugin call** — the agent uses data from Steps 1-3.

**Cross-referencing logic:**
1. Takes each non-compliant `policyDefinitionId` from Step 1
2. Looks up its `displayName` and `description` from Step 2
3. Gets its `nonCompliantResources` count from Step 3
4. Gets its `policyDefinitionCategory` from Step 1 (returned in `QueryPolicyComplianceStates` response)
5. Gets its `timestamp` from Step 1 for age calculation

**Tier assignment example:**
- `"Deploy Microsoft Defender for AI"` → description contains "deploy", "Defender", "security" → targets AI resources → **TIER 1 CRITICAL**
- `"Deploy Microsoft Defender for Storage"` → "deploy", "Defender", "storage" → **TIER 2 HIGH**
- A tagging policy with 1 non-compliant resource detected 2 hours ago → **TIER 4 LOW**

#### STEP 5 → Agent Intelligence: Assess Policy Effect Correctness

**No plugin call** — uses data from Steps 1-3.

For each non-compliant policy, the agent compares:
- **Current effect** (from `policyDefinitionAction` in Step 1, or `effect` in Step 3)
- **Intended behavior** (from `displayName` + `description` in Step 2)

**Example assessment:**
- Policy: `"Require a tag on resources"` — intent is to PREVENT untagged deployments
- Current effect: `audit` — only logs violations, doesn't block
- **Assessment: ⚠️ MISCONFIGURED** → Recommended: `deny`
- Justification: "Policy intent is enforcement ('require') but effect only audits"

#### STEP 6 → Agent Intelligence + Optional Plugin Skill: `TriggerRemediation`

**No automatic plugin call** — the agent generates remediation recommendations.

For each non-compliant policy, the agent provides:

1. **Specific remediation steps** tailored to the resource type
2. **Auto-remediation availability check:**
   - If effect is `deployIfNotExists` or `modify` → "Auto-remediation IS available. Would you like to trigger it?"
   - If effect SHOULD be `deployIfNotExists`/`modify` (from Step 5) → "Auto-remediation WOULD be available once the effect is corrected"
   - Otherwise → Manual remediation steps only
3. **Effect correction steps** (if flagged in Step 5): Azure CLI command or Portal navigation
4. **Effort estimate:** Quick Fix / Medium / Complex

**Only if the user explicitly requests remediation**, the agent calls:
```
PUT /subscriptions/{subscriptionId}/providers/Microsoft.PolicyInsights/remediations/{remediationName}
?api-version=2021-10-01

Body:
{
  "properties": {
    "policyAssignmentId": "<from SummarizeCompliance>",
    "resourceDiscoveryMode": "ExistingNonCompliant"
  }
}
```

#### STEP 7 → Agent Intelligence: Present Results

**No plugin call** — the agent formats all gathered and analyzed data into:

```
🔒 Compliance Prioritization Report
Subscription: <id>
Date: <current date>

Executive Summary:
- Total non-compliant policies: 5
- Policies with misconfigured effects: 1
- Quick-fix opportunities: 3
- Resources affected: 5

🔴 TIER 1 — CRITICAL (2 policies)
[Table with policy details, effect assessment, remediation steps]

🟠 TIER 2 — HIGH (1 policy)
[Table]

🟡 TIER 3 — MEDIUM (1 policy)
[Table]

🟢 TIER 4 — LOW (1 policy)
[Table]

Recommended Next Actions (in order):
1. Fix misconfigured effect on "Require tag on resources" (deny instead of audit)
2. Trigger auto-remediation for Defender for AI deployment
3. ...
```

---

### Data Flow Diagram

```
User Prompt
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  AGENT: Azure Policy Compliance Prioritizer             │
│                                                         │
│  STEP 1 ──► QueryPolicyComplianceStates ──► Raw data    │
│  STEP 2 ──► ListPolicyDefinitions ──────► Policy names  │
│  STEP 3 ──► SummarizeCompliance ────────► Counts        │
│                                                         │
│  STEP 4: Cross-reference + Tier assignment (agent-side) │
│  STEP 5: Effect assessment (agent-side)                 │
│  STEP 6: Remediation recommendations (agent-side)       │
│           └──► TriggerRemediation (only if user asks)   │
│  STEP 7: Format report (agent-side)                     │
│                                                         │
└─────────────────────────────────────────────────────────┘
    │
    ▼
Compliance Prioritization Report
```
