# Context Transfer: Azure Policy Auditor Agent — Session 7 March 2026

**Last Updated:** 2026-03-07
**Repo:** `/Users/yashmudaliar/GitHubRepo-VSCode/SecurityCopilot`
**GitHub:** `the-sentinental-guy/SecurityCopilot`

---

## 1. SESSION OBJECTIVES

Build a Security Copilot custom agent that:
1. Scans all non-compliant Azure policies across a subscription
2. Prioritizes and presents the **top 10** by: effect severity → violation count → non-compliance age
3. Resolves **policy display names** (not GUIDs) via BuiltIn/Custom fallback
4. Provides **targeted, specific remediation** per policy (no generic "review the policy" advice)
5. Presents an Executive Summary with totals, effect distribution, auto-remediable count
6. Stays **under the 128K token limit** of Security Copilot

---

## 2. STATE OF PLAY (end of this session)

### What Exists Now

| File | Purpose | Status |
|------|---------|--------|
| `PolicyAuditor.yaml` (repo root) | **Latest agent manifest** — 2-step, 3 ChildSkills, 566 words | ✅ Ready to test |
| `PolicyPostureAgent.yaml` (repo root) | Previous attempt — 4-step, 5 ChildSkills, 818 words | ❌ Replaced by PolicyAuditor |
| `Plugin Manifest/newManifestAzurePolicy88.yaml` | OpenAPI spec with 8 endpoints | ✅ Active spec |
| `Downloads/AzurePolicyManagerPluginManifest-v88.yaml` | Plugin wrapper pointing to V88 gist | ✅ Active plugin |

### Plugin Manifest (unchanged, working)
- **File:** `AzurePolicyManagerPluginManifest-v88.yaml`
- **Gist URL:** `https://gist.githubusercontent.com/the-sentinental-guy/5b69e664cb36967389eb8680be686c99/raw/c081e539d4ddcad2599efe55a46fe4268f6872c0/newManifestAzurePolicy88.yaml`
- **Spec version:** V88 with 8 operationIds

### Agent Manifest (optimized this session)
- **File:** `PolicyAuditor.yaml`
- **Internal Name:** `PolicyAuditor` (consistent across Descriptor, Skill, AgentDefinition, ProcessSkill)
- **ChildSkills (3 only):** `QueryPolicyComplianceStates`, `GetBuiltInPolicyDefinition`, `GetPolicyDefinition`
- **Icon:** `''` (single quotes, empty string — proven format)
- **Instructions:** 2-step flow, ~566 words

---

## 3. THE TOKEN LIMIT ERROR (the reason for this session's optimizations)

A previous agent run hit the 128K limit:
```
Error occurred during execution of GovernanceAnalyzer: OpenAI request failed: BadRequest (Bad Request) : {
  "error": { "message": "This model's maximum context length is 128000 tokens.
  However, you requested 129003 tokens (95219 in the messages, 1016 in the functions,
  and 32768 in the completion).", "type": "invalid_request_error", "param": "messages",
  "code": "context_length_exceeded" }
}
```

**Token breakdown:**
- 95,219 in messages (instructions + API response payloads)
- 1,016 in functions (ChildSkill definitions from the OpenAPI spec)
- 32,768 in completion (fixed, cannot reduce)
- **Over by 1,003 tokens**

**Root cause:** `SummarizeCompliance` returns 40-60K tokens on large subscriptions. Combined with 5+ ChildSkill function definitions, it exceeded limit.

### How PolicyAuditor solves this:

| Strategy | Token Savings |
|----------|---------------|
| Skip `SummarizeCompliance` entirely | -40,000 to -60,000 tokens |
| Only 3 ChildSkills (not 5-8) | -400 to -600 function tokens |
| `$select` on QueryPolicyComplianceStates (6 fields) | -50% per response record |
| Shorter instructions (566 vs 818+ words) | -300 instruction tokens |
| **Estimated total budget: ~54,000-64,000 tokens** | **~50% of limit** |

---

## 4. AGENT DESIGN: PolicyAuditor.yaml

### Flow (2 steps + report)

**STEP 1 — Scan Non-Compliant Policies (1 API call)**
- `QueryPolicyComplianceStates` with `$filter: ComplianceState eq 'NonCompliant'`, `$top: 100`, `$select: policyDefinitionId,policyDefinitionAction,resourceId,resourceType,resourceGroup,timestamp`
- Groups ALL records by `policyDefinitionId`
- Computes per-policy: violationCount, effect, oldestTimestamp, ageDays, autoRemediable, affectedResources (up to 3)
- Ranks top 10 by: effect severity (deny=4, deployIfNotExists=3, modify=3, auditIfNotExists=2, audit=1) → violationCount desc → ageDays desc

**STEP 2 — Resolve Display Names (10-12 API calls)**
- Calls `GetBuiltInPolicyDefinition` FIRST (most policies are BuiltIn)
- Falls back to `GetPolicyDefinition` with subscriptionId if BuiltIn fails
- Extracts: displayName, description, policyType, metadata.category
- Processes in two batches of 5

**REPORT — Three sections:**
1. **Executive Summary:** Total policies, total resources, effect distribution, auto-remediable count, oldest non-compliance age
2. **Top 10 Non-Compliant Policies:** Per-policy: displayName, category, effect, violation count, age, auto-remediable flag, up to 3 affected resources table, SPECIFIC remediation with CLI command, effort estimate
3. **Top 10 Non-Compliant Resources:** Grouped by resourceId, sorted by policiesViolated desc → ageDays desc, with category mapping

### Remediation Quality Rules
- NEVER generic ("review the policy", "update settings to comply")
- MUST derive from policy displayName + description + affected resourceType
- MUST include one concrete Azure CLI command or Portal navigation path
- Examples baked into instructions for LLM pattern matching

---

## 5. V88 OPENAPI SPEC ENDPOINTS (8 total)

| operationId | Method | Path | Used by PolicyAuditor |
|-------------|--------|------|----------------------|
| `ListPolicyDefinitions` | GET | `/subscriptions/{subId}/.../policyDefinitions` | No |
| `GetPolicyDefinition` | GET | `/subscriptions/{subId}/.../policyDefinitions/{name}` | ✅ (fallback) |
| `GetBuiltInPolicyDefinition` | GET | `/providers/.../policyDefinitions/{name}` | ✅ (primary) |
| `ListPolicyAssignments` | GET | `/subscriptions/{subId}/.../policyAssignments` | No |
| `QueryPolicyComplianceStates` | POST | `/subscriptions/{subId}/.../policyStates/latest/queryResults` | ✅ |
| `SummarizeCompliance` | POST | `/subscriptions/{subId}/.../policyStates/latest/summarize` | No (too expensive) |
| `TriggerRemediation` | PUT | `/subscriptions/{subId}/.../remediations/{name}` | No |
| `TriggerPolicyScan` | POST | `/subscriptions/{subId}/.../triggerEvaluation` | No |

---

## 6. CRITICAL RULES (proven across 14+ iterations)

### Manifest Structure
- `Descriptor.Name` = `Skills[0].Name` = `AgentDefinitions[0].Name` — ALL must match exactly
- `ProcessSkill: {Name}` (single-level for new agents) or `{Name}.{Name}` (old format)
- `Icon: ''` — single quotes, empty string. NOT `""`, NOT `!!str ""`
- `ChildSkills` must be an EXACT SUBSET of spec operationIds — extra = "Check your plugins" error
- Fewer ChildSkills = fewer function tokens = more room for API responses

### Token Management
- `SummarizeCompliance` returns 40-60K tokens on production subscriptions — avoid unless subscription is tiny
- Always use `$select` with `QueryPolicyComplianceStates` — cuts tokens per record by ~50%
- Use `$top: 100` (not 5000) — 100 resource records is enough to identify top 10 policies
- Keep instructions under ~600 words (~800 tokens) — beyond this, LLM reliability drops

### Policy Name Resolution
- Most Azure policies (from Defender for Cloud, Azure Security Benchmark) are **BuiltIn**
- `GetPolicyDefinition` (subscription-scoped) returns `PolicyDefinitionNotFound` for BuiltIn → this is why V3 showed "[Not Found]" for all policies
- `GetBuiltInPolicyDefinition` (provider-scoped, no subscriptionId) resolves them correctly
- Call BuiltIn FIRST, Custom as fallback (reverses V3's broken order)

### What the LLM Cannot Do Reliably
- Keyword-based tier matching (TIER 1-4 with keyword lists) → gets ignored
- Complex arithmetic (age calculations with hours) → wrong results
- Deduplication across multiple API responses → produces incorrect counts
- Following 7-8 step instructions → stops after 3-4 steps
- Composite priority scoring (IMPACT+EFFECT+AGE) → unreliable math

---

## 7. VERSION HISTORY (complete)

| Version | File | ChildSkills | Spec | Status | Failure Reason |
|---------|------|-------------|------|--------|----------------|
| V2 | Agent Manifests/ | 6 | V86 | ❌ | Missing GetPolicyDefinition |
| V3 | Confirmed Working/ | 7 | V87 | ✅ | Worked but showed GUIDs, generic remediation |
| V5 | Agent Manifests/ | 6 | V86 | ❌ | Icon: `""`, name change |
| V6 | Agent Manifests/ | 7 | V87 | ❌ | Name mismatch |
| V7 | Agent Manifests/ | 7 | V87 | Partial | PolicyDefinitionNotFound for BuiltIn |
| V8 | Agent Manifests/ | 8 | V88 | ❌ | Output still poor |
| V9 | Agent Manifests/ | 8 | V88 | ❌ | Instructions too complex |
| V10 | Agent Manifests/ | 9 | V89 | ❌ | 8-step, LLM couldn't follow |
| V11 | Extras/ | 9 | V89 | ❌ | Platform bind error |
| V12-lite | Extras/ | 3 | - | ❌ | Platform error |
| V13-ultra | Extras/ | 3 | - | ❌ | Platform error + contradictory instructions |
| V14 | Agent Manifests/ | 7 | V90 | Created | Previous session, not tested |
| **PolicyAuditor** | **repo root** | **3** | **V88** | **Ready to test** | **Current best candidate** |
| PolicyPostureAgent | repo root | 5 | V88 | Superseded | 4-step, ListPolicyAssignments wasted tokens |

---

## 8. WHAT WENT WRONG IN EARLIER RUNS (screenshots from V3)

The V3-working agent produced these issues (visible in screenshots):
1. **All policies showed "[Not Found]"** — GUIDs displayed instead of displayName because V87 spec lacked `GetBuiltInPolicyDefinition`
2. **All policies ranked Tier 1** — Keyword-tier matching couldn't work without descriptions; even with them, LLM can't reliably keyword-match
3. **Generic remediation** ("review the specific policy intent", "manual remediation required") — Without policy names/descriptions, no context for specific guidance
4. **Only 5 policies sampled** — "batch max 5" instruction caused LLM to stop after one batch
5. **Effect assessment had no value** — Showed "auditifnotexists" and "audit" as effects but marked "Correct" for everything because descriptions were missing

---

## 9. WHAT TO DO NEXT

### Immediate: Test PolicyAuditor
1. Upload `AzurePolicyManagerPluginManifest-v88.yaml` as plugin (if not already active)
2. Upload `PolicyAuditor.yaml` as agent
3. Run with subscription ID: `6b6eb493-e08e-4fee-aa51-91351f9b3e61`
4. Verify: display names resolve, remediation is specific, stays under 128K tokens

### If PolicyAuditor Upload Fails ("Check your plugins")
The platform was blocking all agent uploads as of Feb 2026. If still happening:
1. Create agent manually in Security Copilot UI ("Start from scratch")
2. Add the 3 tools: QueryPolicyComplianceStates, GetBuiltInPolicyDefinition, GetPolicyDefinition
3. Paste the Instructions text from PolicyAuditor.yaml
4. Test → if works, export the generated YAML to learn current schema

### If Token Limit Still Hit
- Reduce `$top` from 100 to 50 in QueryPolicyComplianceStates
- Reduce top policies from 10 to 5
- Remove "Top 10 Non-Compliant Resources" section from report

### If Display Names Still Show GUIDs
- Confirm `GetBuiltInPolicyDefinition` is being called (check runtime logs)
- The BuiltIn endpoint path is `/providers/Microsoft.Authorization/policyDefinitions/{name}` (no subscriptionId)
- If the spec gist is cached, create a new gist with the V88 spec

### Quality Improvements for Future Sessions
- Add an `$orderby: timestamp asc` to QueryPolicyComplianceStates to get oldest violations first
- Consider adding back `SummarizeCompliance` with `$top=1` just for the subscription-level totals (1 call, minimal tokens) — only if token budget allows
- Add a "Recommended Next Actions" section (top 3-5 highest-priority actions)

---

## 10. GIST URLs

```
V86: https://gist.githubusercontent.com/the-sentinental-guy/f0cf49c6553f592f44b5284c920395f7/raw/.../newManifestAzurePolicy86.yaml
V87: https://gist.githubusercontent.com/the-sentinental-guy/560547d7c01802c80f335bb52abd88a2/raw/034c649bb05eb5e7b798d1759af31c57b6f0b305/newManifestAzurePolicy87.yaml
V88: https://gist.githubusercontent.com/the-sentinental-guy/5b69e664cb36967389eb8680be686c99/raw/c081e539d4ddcad2599efe55a46fe4268f6872c0/newManifestAzurePolicy88.yaml
V89: https://gist.githubusercontent.com/the-sentinental-guy/f61105171230490b72d29851bbc59bcd/raw/.../newManifestAzurePolicy89.yaml
```

---

## 11. USER ENVIRONMENT

- **Security Copilot tenants:** Two tested
- **Subscription ID:** `6b6eb493-e08e-4fee-aa51-91351f9b3e61`
- **Known non-compliant policies:** ~5 (all auditIfNotExists/audit effect, affecting ~10 VMs across 2 resource groups)
- **Plugin internal name:** `AzurePolicyManager` (agent's `RequiredSkillsets` must reference this)

---

## 12. FILES CREATED/MODIFIED THIS SESSION

| Action | File |
|--------|------|
| Modified | `PolicyAuditor.yaml` — Optimized instructions, fixed Icon, added age-based ranking, added Executive Summary, added auto-remediable tracking |
| Created (previous turn) | `Agent Manifests/AzurePolicyOptimizerAgent_Version14.yaml` — 5-step design with V90 spec, superseded by PolicyAuditor |
| Created (previous turn) | `Plugin Manifest/newManifestAzurePolicy90.yaml` — Slimmed OpenAPI spec, not needed since V88 already has all required endpoints |
| Created (previous turn) | `Plugin Manifest/AzurePolicyManagerPluginManifest_V2.yaml` — Plugin wrapper for V90, not needed |
| Unchanged | `Downloads/AzurePolicyManagerPluginManifest-v88.yaml` — Active plugin (points to V88 gist) |
| Unchanged | `Plugin Manifest/newManifestAzurePolicy88.yaml` — Active OpenAPI spec |
