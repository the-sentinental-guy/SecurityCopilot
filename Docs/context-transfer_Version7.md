# Context Transfer: Azure Policy Auditor Agent — Session 8 March 2026

**Last Updated:** 2026-03-08
**Repo:** `/Users/yashmudaliar/GitHubRepo-VSCode/SecurityCopilot`
**GitHub:** `the-sentinental-guy/SecurityCopilot`

---

## 1. SESSION OBJECTIVES

Continue development of the Security Copilot custom policy auditor agent:
1. Test the output of `PolicyAuditor.yaml` and confirm it works correctly
2. Create `PolicyAuditorV2.yaml` with three enhancements based on test results
3. Maintain NEVER-reuse-agent-name rule to avoid caching issues

---

## 2. STATE OF PLAY (end of this session)

### What Was Tested This Session

`PolicyAuditor.yaml` was run against subscription `6b6eb493-e08e-4fee-aa51-91351f9b3e61`.
**Result: PASSED.** Output saved in `Docs/Output - Policy Auditor.docx`.

Confirmed working:
- Display names resolve correctly (no GUIDs shown to user)
- Remediation is policy-specific (no generic "review the policy" text)
- No token limit errors (stayed well under 128K)
- Executive Summary totals are accurate
- Top 10 ranking by effect severity → violation count → age works correctly

### What Exists Now

| File | Purpose | Status |
|------|---------|--------|
| `PolicyAuditorV2.yaml` (repo root) | **Latest agent manifest** — 3-step, 4 ChildSkills | ✅ Ready to test |
| `PolicyAuditor.yaml` (repo root) | Previous version — 2-step, 3 ChildSkills, 566 words | ✅ Confirmed working |
| `PolicyPostureAgent.yaml` (repo root) | Earlier attempt — 4-step, 5 ChildSkills | ❌ Superseded |
| `Plugin Manifest/newManifestAzurePolicy88.yaml` | OpenAPI spec with 8 endpoints | ✅ Active spec |
| `Downloads/AzurePolicyManagerPluginManifest-v88.yaml` | Plugin wrapper pointing to V88 gist | ✅ Active plugin |

### Agent Manifest (new this session)
- **File:** `PolicyAuditorV2.yaml`
- **Internal Name:** `PolicyAuditorV2` (consistent across Descriptor, Skill, AgentDefinition, ProcessSkill)
- **DisplayName:** `Policy Auditor V2`
- **ChildSkills (4):** `QueryPolicyComplianceStates`, `GetBuiltInPolicyDefinition`, `GetPolicyDefinition`, `ListPolicyAssignments`
- **Icon:** `''` (single quotes, empty string — proven format)
- **Instructions:** 3-step flow (Step 1, Step 1A, Step 2 + report)

---

## 3. THREE ENHANCEMENTS IN PolicyAuditorV2

### Enhancement 1 — Active Assignment Counts in Executive Summary

**What changed:** Added new STEP 1A that calls `ListPolicyAssignments` (no filter).
Computes `totalActiveAssignments` and `totalUniqueDefinitions` from the response.

**New Executive Summary lines (appear ABOVE existing lines):**
```
- Total active policy assignments: {totalActiveAssignments}
- Total unique policy definitions assigned: {totalUniqueDefinitions}
```

**Why:** Gives leadership-level context — how many policies are *active* vs. how many are
*non-compliant*. Helps communicate scope and compliance posture at a glance.

**Impact on token budget:** `ListPolicyAssignments` returns lightweight assignment objects
(no compliance state data). Estimated +1,000–3,000 tokens. Still well under 128K.

---

### Enhancement 2 — Natural Language Remediation Format

**What changed:** Replaced the CLI-first remediation instructions with a dual-format approach.

**Old format:**
```
Remediation: SPECIFIC to displayName + description + resourceType.
One concrete Azure CLI command or Portal path.
```

**New format:**
```
Remediation: Plain English explanation of what to change and why,
written for someone who may not know CLI. Then a "Quick reference:"
line with ONE Azure CLI command OR Azure Portal navigation.
Effort: Quick Fix (<1hr) / Medium (1-4hr) / Complex (>4hr).
```

**Why:** Security Copilot is used by security analysts and executives — not just engineers.
Plain English first makes remediation accessible to a broader audience. The "Quick reference:"
line preserves the actionable CLI/Portal detail for technical users.

---

### Enhancement 3 — Exempted Resources Follow-Up Support

**What changed:** Added a `FOLLOW-UP — Exempted Resources` section at the end of the
instructions (after TOP 10 NON-COMPLIANT RESOURCES).

**New section:**
```
FOLLOW-UP — Exempted Resources:
If the user asks about exempted or exempt resources for a policy,
call QueryPolicyComplianceStates with:
$filter: ComplianceState eq 'Exempt',
$top: 100,
$select: policyDefinitionId,resourceId,resourceType,resourceGroup,timestamp.
Group by policyDefinitionId, show: Resource Name | Resource Group |
Type | Exempt Since (timestamp).
```

**Why:** A common follow-up after reviewing non-compliant policies is "are any resources
exempt?" This uses the existing `QueryPolicyComplianceStates` ChildSkill — no new skill needed.

---

## 4. CRITICAL RULES (unchanged from previous sessions)

### Manifest Structure
- `Descriptor.Name` = `Skills[0].Name` = `AgentDefinitions[0].Name` — ALL must match exactly
- **NEVER reuse a previous agent name** — causes caching issues requiring full delete/recreate
- `ProcessSkill: {Name}` (single-level for new agents)
- `Icon: ''` — single quotes, empty string. NOT `""`, NOT `!!str ""`
- `ChildSkills` must be EXACT operationIds from the V88 spec — extra = "Check your plugins" error
- Fewer ChildSkills = fewer function tokens = more room for API responses

### Token Management
- `SummarizeCompliance` returns 40-60K tokens on production subscriptions — avoid
- Always use `$select` with `QueryPolicyComplianceStates` — cuts tokens per record by ~50%
- Use `$top: 100` (not 5000) — 100 resource records is enough to identify top 10 policies
- Keep instructions under ~600 words (~800 tokens)

### Policy Name Resolution
- Most Azure policies are **BuiltIn** → call `GetBuiltInPolicyDefinition` FIRST
- `GetPolicyDefinition` (subscription-scoped) → use as fallback only
- Both fail → use GUID as name, category=General

---

## 5. V88 OPENAPI SPEC ENDPOINTS (8 total)

| operationId | Method | Path | Used by PolicyAuditorV2 |
|-------------|--------|------|-------------------------|
| `ListPolicyDefinitions` | GET | `/subscriptions/{subId}/.../policyDefinitions` | No |
| `GetPolicyDefinition` | GET | `/subscriptions/{subId}/.../policyDefinitions/{name}` | ✅ (fallback) |
| `GetBuiltInPolicyDefinition` | GET | `/providers/.../policyDefinitions/{name}` | ✅ (primary) |
| `ListPolicyAssignments` | GET | `/subscriptions/{subId}/.../policyAssignments` | ✅ (Step 1A) |
| `QueryPolicyComplianceStates` | POST | `/subscriptions/{subId}/.../policyStates/latest/queryResults` | ✅ |
| `SummarizeCompliance` | POST | `/subscriptions/{subId}/.../policyStates/latest/summarize` | No (too expensive) |
| `TriggerRemediation` | PUT | `/subscriptions/{subId}/.../remediations/{name}` | No |
| `TriggerPolicyScan` | POST | `/subscriptions/{subId}/.../triggerEvaluation` | No |

---

## 6. VERSION HISTORY (complete)

| Version | File | ChildSkills | Spec | Status | Notes |
|---------|------|-------------|------|--------|-------|
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
| PolicyAuditor | repo root | 3 | V88 | ✅ Confirmed working | Display names resolve, specific remediation, no token errors |
| **PolicyAuditorV2** | **repo root** | **4** | **V88** | **Ready to test** | 3 enhancements: assignments summary, NL remediation, exempt follow-up |
| PolicyPostureAgent | repo root | 5 | V88 | Superseded | 4-step, ListPolicyAssignments wasted tokens |

---

## 7. WHAT TO DO NEXT

### Immediate: Test PolicyAuditorV2
1. Ensure `AzurePolicyManagerPluginManifest-v88.yaml` plugin is already active (no changes to plugin needed)
2. Upload `PolicyAuditorV2.yaml` as a **new** agent (do NOT overwrite PolicyAuditor)
3. Run with subscription ID: `6b6eb493-e08e-4fee-aa51-91351f9b3e61`
4. Verify:
   - Executive Summary now shows two new lines (active assignments, unique definitions)
   - Remediation has plain English + "Quick reference:" line
   - No token limit errors (4 ChildSkills still well under 128K)

### If Token Limit Is Hit
- Remove the FOLLOW-UP section (saves ~60 tokens)
- Reduce `$top` from 100 to 50 in QueryPolicyComplianceStates
- `ListPolicyAssignments` is the new call — if its response is large, add `$top: 200`

### If "Check Your Plugins" Error on Upload
- Verify all 4 ChildSkill names match exact operationIds in V88 spec:
  `QueryPolicyComplianceStates`, `GetBuiltInPolicyDefinition`, `GetPolicyDefinition`, `ListPolicyAssignments`
- Confirm agent internal name is `PolicyAuditorV2` (not `PolicyAuditor`)

### Quality Improvements for Future Sessions
- Add `$orderby: timestamp asc` to QueryPolicyComplianceStates to surface oldest violations
- Consider a "Recommended Next Actions" section (top 3 highest-priority remediation items)
- Consider adding `TriggerRemediation` as optional 5th ChildSkill for one-click remediation of `deployIfNotExists` policies

---

## 8. FILES CREATED/MODIFIED THIS SESSION

| Action | File |
|--------|------|
| Created | `PolicyAuditorV2.yaml` — New agent with 4 ChildSkills and 3 enhancements |
| Created | `Docs/context-transfer_Version7.md` — This document |
| Unchanged | `PolicyAuditor.yaml` — Confirmed working, do not modify |
| Unchanged | `Plugin Manifest/newManifestAzurePolicy88.yaml` — Active OpenAPI spec |

---

## 9. GIST URLS

```
V86: https://gist.githubusercontent.com/the-sentinental-guy/f0cf49c6553f592f44b5284c920395f7/raw/.../newManifestAzurePolicy86.yaml
V87: https://gist.githubusercontent.com/the-sentinental-guy/560547d7c01802c80f335bb52abd88a2/raw/034c649bb05eb5e7b798d1759af31c57b6f0b305/newManifestAzurePolicy87.yaml
V88: https://gist.githubusercontent.com/the-sentinental-guy/5b69e664cb36967389eb8680be686c99/raw/c081e539d4ddcad2599efe55a46fe4268f6872c0/newManifestAzurePolicy88.yaml
V89: https://gist.githubusercontent.com/the-sentinental-guy/f61105171230490b72d29851bbc59bcd/raw/.../newManifestAzurePolicy89.yaml
```

---

## 10. USER ENVIRONMENT

- **Security Copilot tenants:** Two tested
- **Subscription ID:** `6b6eb493-e08e-4fee-aa51-91351f9b3e61`
- **Known non-compliant policies:** ~5 (all auditIfNotExists/audit effect, affecting ~10 VMs across 2 resource groups)
- **Plugin internal name:** `AzurePolicyManager` (agent's `RequiredSkillsets` must reference this)
