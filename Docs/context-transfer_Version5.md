# Context Transfer: Azure Policy Compliance Prioritizer — Security Copilot Plugin & Agent

## Project Overview

I am building a **custom API plugin** for **Microsoft Security Copilot** that queries Azure Policy compliance data, paired with a **custom Security Copilot Agent** that uses the plugin's skills to perform multi-step compliance analysis, prioritization, and remediation recommendations.

The project has two components:
1. **API Plugin** — An OpenAPI 3.0 manifest (`newManifestAzurePolicy86.yaml`) deployed via a Security Copilot plugin manifest wrapper (`AzurePolicyManagerPluginManifest.yaml`)
2. **Agent** — A Security Copilot custom agent (`agent-instructions.md`) that orchestrates 7-step analysis using the plugin's API skills

**Repository:** `YashMudaliarIN/SecurityCopilotTest`

---

## Current Working State

The plugin is **fully functional and tested in production** in Security Copilot. It correctly:
- Lists compliant policies (via `SummarizeCompliance`)
- Lists non-compliant policies (via `SummarizeCompliance`)
- Returns per-definition compliance counts within initiatives
- Plugin selection time: ~6 seconds
- Query + response time: ~12 seconds total

The agent instructions are **finalized** and ready for deployment.

---

## Plugin Manifest Wrapper

**File: `AzurePolicyManagerPluginManifest.yaml`**

```yaml
Descriptor:
  Name: AzurePolicyManager
  DisplayName: AzurePolicy Yashure
  Description: Plugin to query Azure Policy definitions, retrieve compliance states, list unhealthy resources, trigger evaluations, and generate compliance summaries.
  DescriptionForModel: Use this plugin to access Azure Policy data. It can retrieve lists of non-compliant (unhealthy) resources, summarize compliance states for reporting, list policy definitions, and trigger compliance scans.
  SupportedAuthTypes:
    - AADDelegated
  Authorization:
    Type: AADDelegated
    EntraScopes: https://management.azure.com/user_impersonation
SkillGroups:
  - Format: API
    Settings:
      OpenApiSpecUrl: <Gist raw URL hosting newManifestAzurePolicy86.yaml>
```

**Critical notes about the wrapper:**
- `Icon` field is NOT supported in Security Copilot plugin manifests — including it causes upload failures
- `DescriptionForModel` is critical for plugin/skill routing — don't remove it
- Auth is `AADDelegated` with `user_impersonation` scope — uses the logged-in user's Azure permissions
- When updating the OpenAPI spec URL, you MUST delete and re-add the plugin entirely in Security Copilot — it caches the spec aggressively

---

## OpenAPI Manifest: `newManifestAzurePolicy86.yaml`

### 6 Operations

All operations target `https://management.azure.com`.

#### 1. `ListPolicyDefinitions` (GET)
- **Path:** `/subscriptions/{subscriptionId}/providers/Microsoft.Authorization/policyDefinitions`
- **api-version:** `2023-04-01`
- **Response schema declares:** `id`, `properties.displayName`, `properties.description`, `properties.policyType`
- **Note:** `subscriptionId` description is short: `"The Azure Subscription ID."` — this works fine

#### 2. `ListPolicyAssignments` (GET)
- **Path:** `/subscriptions/{subscriptionId}/providers/Microsoft.Authorization/policyAssignments`
- **api-version:** `2023-04-01`
- **Response schema declares:** `id`, `name`, `properties.scope`, `properties.policyDefinitionId`

#### 3. `QueryPolicyComplianceStates` (POST)
- **Path:** `/subscriptions/{subscriptionId}/providers/Microsoft.PolicyInsights/policyStates/latest/queryResults`
- **api-version:** `2019-10-01` (pinned via `enum: ["2019-10-01"]` + `default`)
- **Has `requestBody: required: false`** with empty `application/json` schema — CRITICAL for Security Copilot POST call construction
- **Parameters:** `$filter`, `$top`, `$orderby`, `$select`
- **`$filter` description notes:** Field names must use PascalCase (e.g., `ComplianceState`, not `complianceState`)
- **Response schema declares:** `timestamp`, `resourceId`, `policyAssignmentId`, `policyAssignmentName`, `policyAssignmentScope`, `policyDefinitionId`, `policyDefinitionName`, `policyDefinitionAction`, `policyDefinitionCategory`, `policySetDefinitionId`, `policySetDefinitionName`, `policySetDefinitionCategory`, `complianceState` (enum), `subscriptionId`, `resourceType`, `resourceLocation`, `resourceGroup`, `resourceTags`, `policyAssignmentParameters`, `complianceReasonCode`, `managementGroupIds`, `@odata.nextLink`

#### 4. `SummarizeCompliance` (POST)
- **Path:** `/subscriptions/{subscriptionId}/providers/Microsoft.PolicyInsights/policyStates/latest/summarize`
- **api-version:** `2019-10-01` (pinned via `enum`)
- **Has `requestBody: required: false`** with empty schema
- **Parameters:** `$top`, `$filter`
- **Response schema declares nested structure:**
  - `value[].results.nonCompliantResources` / `nonCompliantPolicies` (subscription-level aggregate)
  - `value[].policyAssignments[].policyAssignmentId`
  - `value[].policyAssignments[].policySetDefinitionId`
  - `value[].policyAssignments[].policyDefinitions[].policyDefinitionId`
  - `value[].policyAssignments[].policyDefinitions[].policyDefinitionReferenceId`
  - `value[].policyAssignments[].policyDefinitions[].effect`
  - `value[].policyAssignments[].policyDefinitions[].results.nonCompliantResources`
- **Key logic:** A definition is compliant if `nonCompliantResources` is `0`

#### 5. `TriggerRemediation` (PUT)
- **Path:** `/subscriptions/{subscriptionId}/providers/Microsoft.PolicyInsights/remediations/{remediationName}`
- **api-version:** `2021-10-01`
- **Request body:** `properties.policyAssignmentId` (required), `properties.policyDefinitionReferenceId` (for initiative-specific remediation), `properties.resourceDiscoveryMode`
- **Agent should only SUGGEST remediation, not auto-trigger it**

#### 6. `TriggerPolicyScan` (POST)
- **Path:** `/subscriptions/{subscriptionId}/providers/Microsoft.PolicyInsights/policyStates/latest/triggerEvaluation`
- **api-version:** `2019-10-01`
- **Response:** 202 Accepted with Location header

---

## HARD-WON LESSONS — Security Copilot Plugin Parsing Rules

These were discovered through extensive trial-and-error. Violating any of these causes plugin failures:

### 1. `subscriptionId` Description Sensitivity
- Long descriptions with GUID examples (`"This is a GUID such as a1b2c3d4-e5f6-7890-abcd-ef1234567890. Extract this value from the user's query."`) work on MOST operations
- The `ListPolicyDefinitions` operation uses a SHORT description (`"The Azure Subscription ID."`) and this also works
- NEVER use a real subscription ID as an example in the manifest

### 2. `requestBody` Required on POST Operations
- `QueryPolicyComplianceStates` and `SummarizeCompliance` are POST endpoints
- They MUST have `requestBody: required: false` with an empty `application/json` schema declared
- Without this, Security Copilot cannot construct the POST call — results in "resource type not found" errors

### 3. `api-version` Must Be Pinned with `enum` for PolicyInsights Operations
- Use `enum: ["2019-10-01"]` combined with `default: "2019-10-01"` for PolicyInsights endpoints
- Without `enum`, Security Copilot may substitute a different API version

### 4. OData `$filter` PascalCase Requirement
- Filter field names MUST use PascalCase: `ComplianceState`, `PolicyDefinitionId`, NOT `complianceState`
- Wrong casing returns empty results or errors

### 5. Response Schema Depth Limits
- Security Copilot's parser has limits on nesting depth
- The `SummarizeCompliance` nested response (5 levels: `value[].policyAssignments[].policyDefinitions[].results.nonCompliantResources`) works
- But adding additional deeply nested objects (like `metadata.category` inside `ListPolicyDefinitions`) was found to break plugin loading entirely
- Keep response schemas as flat as possible

### 6. Description Length Affects Plugin Selection Speed
- Minimal descriptions = faster plugin selection (6 seconds)
- Overly verbose descriptions = slow plugin selection (51 seconds) or failure
- Descriptions CAN include skill routing hints (e.g., "When a user asks to list compliant policies, this is the correct operation") — this was proven to work on `SummarizeCompliance`

### 7. Plugin Caching
- Security Copilot caches the OpenAPI spec
- When changing the Gist URL or updating spec content, ALWAYS: disable plugin → delete plugin → re-upload manifest → enable → test in a NEW session

### 8. `Icon` Field Not Supported
- The `Descriptor` section does NOT support an `Icon` field
- Including it causes plugin upload failures in Security Copilot

### 9. `@odata` Properties Must Be Quoted
- Response properties like `@odata.context`, `@odata.count`, `@odata.nextLink` must be quoted in YAML: `'@odata.context'`

---

## Agent Instructions Summary

The agent follows a 7-step workflow:

1. **Step 1:** Call `QueryPolicyComplianceStates` with `$filter=ComplianceState eq 'NonCompliant'` and `$top=5000` — gets all non-compliant resource records
2. **Step 2:** Call `ListPolicyDefinitions` — gets displayName, description, policyType for each definition
3. **Step 3:** Call `SummarizeCompliance` with `$top=50` — gets per-definition nonCompliantResources counts and effects
4. **Step 4:** Prioritize by policy INTENT (not effect) using 4-tier framework: 🔴 CRITICAL → 🟠 HIGH → 🟡 MEDIUM → 🟢 LOW — based on category (from Step 1 `policyDefinitionCategory`), displayName/description keywords (from Step 2), resource criticality (from Step 1 `resourceType`), resource count (from Step 3), and age (from Step 1 `timestamp`)
5. **Step 5:** Assess effect correctness — compare current effect (`policyDefinitionAction` from Step 1, `effect` from Step 3) against policy intent (displayName/description from Step 2). Flag as MISCONFIGURED if prevention-intent uses audit, monitor-intent uses deny, auto-deploy-intent uses audit/deny, or disabled but actively assigned. Extra scrutiny for Custom policies.
6. **Step 6:** Recommend remediation — specific steps, auto-remediation availability (for deployIfNotExists/modify effects), effect correction CLI/Portal commands, effort estimates. **NEVER auto-trigger TriggerRemediation** — only execute if user explicitly asks.
7. **Step 7:** Format as Compliance Prioritization Report with executive summary, per-tier tables, and recommended next actions.

**Key data source mapping:**
- Policy CATEGORY → `policyDefinitionCategory` from `QueryPolicyComplianceStates` (Step 1) — NOT from `ListPolicyDefinitions`
- Policy EFFECT → `policyDefinitionAction` from `QueryPolicyComplianceStates` (Step 1) AND `effect` from `SummarizeCompliance` (Step 3) — NOT from `ListPolicyDefinitions` (`policyRule.then.effect` is not in schema)
- Policy NAME/DESCRIPTION/TYPE → `ListPolicyDefinitions` (Step 2)
- Resource COUNT per definition → `SummarizeCompliance` nested `policyDefinitions[].results.nonCompliantResources` (Step 3)

---

## Test Environment

- **Subscription ID:** [User will provide when testing — never hardcode a real subscription ID in manifests]
- **Active assignment:** One initiative assignment containing 12 Defender-related policy definitions
- **Compliance state:** 7 compliant definitions, 5 non-compliant definitions
- **All non-compliant policies have effect:** `deployIfNotExists`

---

## What's Next

The user needs to:
1. Finalize and deploy the agent instructions in Security Copilot
2. Test the agent's 7-step workflow end-to-end
3. Validate that the agent correctly prioritizes, assesses effects, and generates the report
4. Test remediation triggering (only when explicitly asked)

The OpenAPI manifest (`newManifestAzurePolicy86.yaml`) and plugin wrapper (`AzurePolicyManagerPluginManifest.yaml`) are finalized and working — do NOT modify them unless a specific test reveals a new issue.