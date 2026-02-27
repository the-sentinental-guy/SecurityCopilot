# Azure Policy Agent — Full Session Context Summary

**Last Updated:** 2026-02-27T15:46:00+05:30
**Repo:** `/Users/yashmudaliar/GitHubRepo-VSCode/SecurityCopilot`
**GitHub:** `the-sentinental-guy/SecurityCopilot`

---

## 1. PROJECT GOAL

Build an enterprise-ready Azure Policy analysis agent for **Microsoft Security Copilot** that:
- Provides a compliance score
- Shows top 10 non-compliant policies ranked by effect severity + resource count
- Shows top 10 non-compliant resources with age and category
- Lists exemptions relevant to top policies
- Outputs an HTML executive summary
- Uses a fixed ~22 API calls (scales to 200+ policy assignments)

---

## 2. ARCHITECTURE OVERVIEW

### Two Components
1. **Plugin Manifest** (`AzurePolicyManagerPluginManifest.yaml`) — Defines the `AzurePolicyManager` plugin pointing to an OpenAPI spec (hosted on GitHub Gist)
2. **Agent Manifest** (e.g., `AzurePolicyOptimizerAgent_Version11.yaml`) — Defines the agent with instructions and references ChildSkills from the plugin

### How They Connect
- Agent's `Prerequisites: ['AzurePolicyManager']` links to the plugin's `Descriptor.Name: AzurePolicyManager`
- Agent's `RequiredSkillsets: ['AzurePolicyManager']` in AgentDefinitions does the same
- Agent's `ChildSkills` list must be a SUBSET of the plugin's OpenAPI spec `operationId` values
- If ANY ChildSkill doesn't match a spec operationId → "Check your plugins" error

### Plugin Upload Flow
1. Upload plugin manifest YAML → Security Copilot loads the OpenAPI spec from the Gist URL
2. Upload agent manifest YAML → Security Copilot resolves each ChildSkill against enabled plugins
3. At runtime, agent calls ChildSkills which map to the API endpoints in the spec

---

## 3. OPENAPI SPEC VERSIONS

All specs are OpenAPI 3.0.0, server: `https://management.azure.com`

| Spec File | Endpoints | Key Additions |
|-----------|-----------|---------------|
| `newManifestAzurePolicy86.yaml` | 6 | Base set (no GetPolicyDefinition) |
| `newManifestAzurePolicy87.yaml` | 7 | + `GetPolicyDefinition` |
| `newManifestAzurePolicy88.yaml` | 8 | + `GetBuiltInPolicyDefinition` |
| `newManifestAzurePolicy89.yaml` | 9 | + `ListPolicyExemptions` |

### Base 6 Endpoints (all specs)
1. `ListPolicyDefinitions` — `/subscriptions/{subscriptionId}/providers/Microsoft.Authorization/policyDefinitions`
2. `ListPolicyAssignments` — `/subscriptions/{subscriptionId}/providers/Microsoft.Authorization/policyAssignments`
3. `QueryPolicyComplianceStates` — `/subscriptions/{subscriptionId}/providers/Microsoft.PolicyInsights/policyStates/latest/queryResults`
4. `SummarizeCompliance` — `/subscriptions/{subscriptionId}/providers/Microsoft.PolicyInsights/policyStates/latest/summarize`
5. `TriggerRemediation` — POST, creates remediation task
6. `TriggerPolicyScan` — POST, forces compliance re-scan

### Added Endpoints
7. `GetPolicyDefinition` (V87+) — `/subscriptions/{subscriptionId}/providers/Microsoft.Authorization/policyDefinitions/{policyDefinitionName}` — Gets displayName, description, metadata.category for custom/subscription-scoped policies
8. `GetBuiltInPolicyDefinition` (V88+) — `/providers/Microsoft.Authorization/policyDefinitions/{policyDefinitionName}` — Same but for BuiltIn policies (no subscriptionId in path). Needed because `GetPolicyDefinition` returns `PolicyDefinitionNotFound` for BuiltIn policies.
9. `ListPolicyExemptions` (V89+) — `/subscriptions/{subscriptionId}/providers/Microsoft.Authorization/policyExemptions` — Lists policy exemptions with category (Waiver/Mitigated), expiration, applicable policyAssignmentId

### Gist URLs
```
V86: https://gist.githubusercontent.com/the-sentinental-guy/f0cf49c6553f592f44b5284c920395f7/raw/e02be23dbeb96237ad70535e7ef623a2459c7b43/newManifestAzurePolicy86.yaml
V87: https://gist.githubusercontent.com/the-sentinental-guy/560547d7c01802c80f335bb52abd88a2/raw/034c649bb05eb5e7b798d1759af31c57b6f0b305/newManifestAzurePolicy87.yaml
V89: https://gist.githubusercontent.com/the-sentinental-guy/f61105171230490b72d29851bbc59bcd/raw/71e3ccc1f6442931c08df584bf929e7cb0abbe6c/newManifestAzurePolicy89.yaml
```
(V88 Gist URL not confirmed — local file exists but no known Gist URL)

---

## 4. AGENT VERSION HISTORY

### Working Baseline: `AzurePolicyOptimizerAgentV3-working.yaml`
- **Status:** LAST CONFIRMED WORKING (produced output, though with known data issues)
- **Internal Name:** `AzurePolicyOptimizerAgentV3`
- **ChildSkills:** 7 (matches V87 spec)
- **Instructions:** 7-step "Compliance Prioritizer" with tier-based prioritization
- **Plugin used with:** V87 spec
- **Key structural properties that made it work:**
  - `CatalogScope: Workspace`
  - `CanToggle: true`
  - `Icon: ''` (single quotes, empty string)
  - `Descriptor.Name` = `SkillGroups.Skills[0].Name` = `AgentDefinitions[0].Name` = `AzurePolicyOptimizerAgentV3`
  - `ProcessSkill: AzurePolicyOptimizerAgentV3.AzurePolicyOptimizerAgentV3`

### Version Progression

| Version | ChildSkills | Spec | Status | Key Problem |
|---------|-------------|------|--------|-------------|
| V2 | 6 | V86 | ❌ Failed | Missing `GetPolicyDefinition` in ChildSkills |
| V3 (working) | 7 | V87 | ✅ Worked | Baseline — but output had data issues |
| V5 | 6 | V86 | ❌ Plugin bind error | Changed Name to V5, Icon to `""` (double quotes) |
| V6 | 7 | V87 | ❌ | Name was `AzurePolicyOptimizerAgent` (no V3 suffix) |
| V7 | 7 | V87 | Partial | Output showed GUIDs instead of displayNames, 5 `PolicyDefinitionNotFound` errors for BuiltIn policies |
| V8 | 8 | V88 | ❌ | Added `GetBuiltInPolicyDefinition` to ChildSkills but output still poor |
| V9 | 8 | V88 | ❌ | Deduplication/batch attempt, instructions too complex (~3000 tokens) |
| V10 | 9 | V89 | ❌ | 8-step instructions, added exemptions. LLM couldn't follow |
| V11 | 9 | V89 | ❌ Plugin bind | Simplified 5-step, but 9 ChildSkills caused binding issues |
| V11-lite | 7 | V87 | ❌ Plugin bind | Reduced to 7 ChildSkills but STILL failed — the entire platform stopped working |

### Output Issues Observed (from V3/V7 runs that produced output)
1. **GUIDs instead of displayNames** — `GetPolicyDefinition` returns `PolicyDefinitionNotFound` for BuiltIn policies (most Azure policies via Defender initiatives are BuiltIn)
2. **Category shows "tbd"** — `QueryPolicyComplianceStates` returns `policyDefinitionCategory: tbd` for many policies
3. **Only 4-5 policies analyzed** — LLM stopped processing before reaching all non-compliant policies
4. **Old V3 instructions ran despite new YAML uploaded** — Runtime logs showed 7 skills resolved even after V11 (9 skills) was uploaded. Confirmed via `$top=50` in logs vs V11's `$top=5`

---

## 5. KNOWN ISSUES AND WHAT NOT TO DO

### ❌ DO NOT change the internal `Name` field
- Changing `Descriptor.Name` from `AzurePolicyOptimizerAgentV3` to anything else (e.g., `AzurePolicyOptimizerAgentV11`) causes "Check your plugins" error
- The Name must be consistent across: `Descriptor.Name`, `SkillGroups.Skills[0].Name`, `AgentDefinitions[0].Name`, and `ProcessSkill: {Name}.{Name}`
- The `DisplayName` CAN be changed freely (it's just UI label)

### ❌ DO NOT use more ChildSkills than the plugin spec has
- If the agent lists 9 ChildSkills but the plugin spec only has 7 operationIds → "Check your plugins"
- ChildSkills must be an EXACT SUBSET of spec operationIds

### ❌ DO NOT write complex multi-step instructions
- The LLM in Security Copilot cannot follow instructions longer than ~50-60 lines reliably
- Tier-based prioritization (TIER 1/2/3/4 with keyword lists) gets ignored
- Complex arithmetic (calculate age in days/hours) produces wrong results
- Deduplication across multiple API responses is unreliable
- V2-V10 all had instruction complexity as the root failure

### ❌ DO NOT rely on `Icon: ""` (double quotes)
- The working V3 uses `Icon: ''` (single quotes)
- Not confirmed as a breaking change but V5 used `""` and failed

### ❌ DO NOT assume Security Copilot updates agent instructions on re-upload
- The V11 runtime proved that even after uploading new YAML with the same Name, the OLD instructions ran
- The Build UI showed 9 tools, but the runtime resolved only 7 skills with old `$top=50`
- This is likely a server-side caching issue

### ✅ DO use effect-based importance (simple)
- `deny` > `deployIfNotExists` > `auditIfNotExists` > `audit`
- Within same effect, higher `nonCompliantResources` first
- This replaces the complex TIER 1-4 system that the LLM couldn't follow

### ✅ DO use `$top=5` on SummarizeCompliance
- Gets enough policyAssignment data while keeping token count low
- Top-level `results` still give accurate subscription-wide totals regardless of `$top`

### ✅ DO use policyDefinitionName/policyDefinitionCategory from QueryPolicyComplianceStates as fallback
- When `GetPolicyDefinition` fails (BuiltIn policies), these fields from `QueryPolicyComplianceStates` provide partial data
- `policyDefinitionCategory` is often "tbd" though — may need to infer from displayName

---

## 6. CURRENT BLOCKER (as of 2026-02-27)

**ALL agent uploads fail with "Check your plugins and make sure the right ones are turned on."**

This affects:
- V11 (9 ChildSkills) ❌
- V11-lite (7 ChildSkills) ❌
- ROLLBACK V3 (exact byte-copy of last working agent) ❌
- Tested on TWO DIFFERENT Security Copilot tenants ❌

### What was verified:
- Files are byte-identical to originals (MD5 match)
- No BOM or encoding issues
- Gist URLs return HTTP 200 with valid YAML
- All ChildSkills match spec operationIds exactly
- Git shows no modifications to the working V3 file

### Suspected cause:
**Microsoft Security Copilot platform update** — web search confirms manifest schema changes in November 2025:
- New fields added: `PromptSkill` in AgentDefinitions, `Interfaces` and `SuggestedPrompts` in Skills
- `LogicApp` format added
- Previously optional fields may now be required

### Recommended next step:
1. Create an agent manually through the Security Copilot "Start from scratch" UI
2. Configure it with the AzurePolicyManager plugin
3. Add the 7 tools manually and test
4. If it works, click "View code" toggle and export the generated YAML
5. This will reveal the current expected manifest schema
6. Update our V11 YAML to match the new schema

---

## 7. KEY API BEHAVIORS

### SummarizeCompliance
- Returns compliance summary broken down by policyAssignment → policyDefinition
- Top-level `results` field has accurate subscription-wide totals (nonCompliantPolicies, nonCompliantResources) regardless of `$top`
- `$top` controls how many policyAssignment summaries are returned
- Each policyAssignment contains `policyDefinitions[]` with individual policy compliance counts
- Fields per definition: `policyDefinitionId`, `effect`, `results.nonCompliantResources`, `policyDefinitionReferenceId`

### GetPolicyDefinition
- Returns `PolicyDefinitionNotFound` for BuiltIn policies (they're at provider level, not subscription level)
- Returns: `properties.displayName`, `properties.description`, `properties.policyType`, `properties.metadata.category`
- Most Azure policies from Defender for Cloud initiatives are BuiltIn → this call fails for them

### GetBuiltInPolicyDefinition (V88+)
- Same response as GetPolicyDefinition but at `/providers/` path (no subscriptionId)
- Handles the BuiltIn policies that GetPolicyDefinition can't find
- Path: `/providers/Microsoft.Authorization/policyDefinitions/{policyDefinitionName}`

### QueryPolicyComplianceStates
- Returns per-resource compliance records
- Useful fields: `resourceId`, `resourceType`, `resourceGroup`, `timestamp`, `policyDefinitionAction`, `policyDefinitionName`, `policyDefinitionCategory`, `policyAssignmentId`
- `policyDefinitionCategory` is often "tbd" for BuiltIn policies
- `policyDefinitionName` is the GUID (not display name)
- Use `$filter: ComplianceState eq 'NonCompliant' and PolicyDefinitionId eq '{id}'` (PascalCase required)

### ListPolicyExemptions (V89+)
- Returns all exemptions in the subscription
- Fields: `displayName`, `policyAssignmentId`, `policyDefinitionReferenceIds[]`, `exemptionCategory` (Waiver/Mitigated), `expiresOn`
- api-version: `2022-07-01-preview`

---

## 8. V11 DESIGN (READY TO IMPLEMENT ONCE PLATFORM ISSUE IS RESOLVED)

### 5-Step Flow (~1,200 tokens)
1. **Compliance Overview** — `SummarizeCompliance($top=5)` → get totals, find top 10 non-compliant policies sorted by effect importance
2. **Policy Details** — `GetPolicyDefinition` (fallback to `GetBuiltInPolicyDefinition` or `policyDefinitionName`) → displayName, category
3. **Affected Resources** — `QueryPolicyComplianceStates` per policy ($top=3, two batches of 5) → resource details, timestamps
4. **Exemptions** — `ListPolicyExemptions` once → match to top 10 policies
5. **Output** — 5 sections: Compliance Score, Top 10 Policies, Top 10 Resources, Exemptions, HTML Summary

### Output Sections
- **SECTION A — COMPLIANCE SCORE:** Percentage, counts
- **SECTION B — TOP 10 NON-COMPLIANT POLICIES:** Per-policy subsection with resource table, CLI remediation, effort estimate
- **SECTION C — TOP 10 NON-COMPLIANT RESOURCES:** Deduplicated, sorted by policy violation count, with age/category
- **SECTION D — EXEMPTIONS:** Matched to top 10 policies
- **SECTION E — HTML EXECUTIVE SUMMARY:** Sentinel-style dark theme, self-contained HTML in code block

### API Call Budget
- 1 SummarizeCompliance
- 10 GetPolicyDefinition (2 batches of 5)
- Up to 10 GetBuiltInPolicyDefinition (fallback)
- 10 QueryPolicyComplianceStates (2 batches of 5)
- 1 ListPolicyExemptions
- **Total: ~22-32 calls max**

---

## 9. FILE INVENTORY

### Agent Files (in repo)
| File | Internal Name | ChildSkills | Status |
|------|--------------|-------------|--------|
| `AzurePolicyOptimizerAgentV3-working.yaml` | AzurePolicyOptimizerAgentV3 | 7 | ✅ Last confirmed working |
| `ROLLBACK_Agent_V3.yaml` | AzurePolicyOptimizerAgentV3 | 7 | Byte-copy of above |
| `AzurePolicyOptimizerAgent_Version11.yaml` | AzurePolicyOptimizerAgentV3 | 9 | V11 full (needs V89 spec) |
| `AzurePolicyOptimizerAgent_Version11_lite.yaml` | AzurePolicyOptimizerAgentV3 | 7 | V11 instructions, 7 skills |
| `AzurePolicyOptimizerAgent_Version10.yaml` | AzurePolicyOptimizerAgentV3 | 9 | V10 (8-step, too complex) |
| `AzurePolicyOptimizerAgent_Version9.yaml` | AzurePolicyOptimizerAgentV3 | 8 | V9 (dedup attempt) |
| `AzurePolicyOptimizerAgent_Version8.yaml` | AzurePolicyOptimizerAgentV3 | 8 | V8 (BuiltIn fallback) |
| `AzurePolicyOptimizerAgent_Version7.yaml` | AzurePolicyOptimizerAgentV3 | 7 | V7 (first V3-based rewrite) |

### Plugin Files
| File | Spec URL |
|------|----------|
| `ROLLBACK_PluginManifest_V87.yaml` | V87 Gist |
| `AzurePolicyManagerPluginManifest.yaml` | V87 Gist (reverted) |
| `Downloads/AzurePolicyManagerPluginManifest (1).yaml` | V87 Gist |
| `Downloads/AzurePolicyManagerPluginManifest.yaml` | V89 Gist |
| `Downloads/AzurePolicyManagerPluginManifest-v88.yaml` | V89 Gist |

### OpenAPI Spec Files (local)
| File | Endpoints |
|------|-----------|
| `newManifestAzurePolicy86.yaml` | 6 (base, no GetPolicyDefinition) |
| `newManifestAzurePolicy87.yaml` | 7 (+ GetPolicyDefinition) |
| `newManifestAzurePolicy88.yaml` | 8 (+ GetBuiltInPolicyDefinition) |
| `newManifestAzurePolicy89.yaml` | 9 (+ ListPolicyExemptions) |

### Other Files
- `Agent V11 Run Time Logs.docx` — Runtime logs from a test session (showed old V3 agent instructions ran despite V11 being uploaded)
- `AzurePolicyCompliancePrioritizerAgent.yaml` — Earlier standalone version
- `AzurePolicyOptimizerAgent.yaml` — Original pre-V2 version

---

## 10. USER ENVIRONMENT

- **Security Copilot instances:** Two different tenants tested
- **User login:** `secadmin@MngEnvMCAP7...`
- **Subscription ID used for testing:** `6b6eb493-e08e-4fee-aa51-91351f9b3e61`
- **Non-compliant policies in subscription:** 4 (with ~10 total affected resources)
- **Plugin display name in Security Copilot:** "YashurePolicy Azure"
- **Plugin internal name:** `AzurePolicyManager`

---

## 11. HTML EXECUTIVE SUMMARY TEMPLATE

The V11 design includes a Sentinel-style HTML report with:
- Dark gradient header (`linear-gradient(135deg, #0f172a, #020617)`)
- Large compliance score display (48px, color-coded: green >80%, orange 50-80%, red <50%)
- Section boxes with blue left border (`#2563eb`)
- Dark table headers (`#020617`)
- Compact policy table (top 5 only in HTML)
- Footer: "Generated by Microsoft Security Copilot - Azure Policy"

---

## 12. RUNTIME LOG ANALYSIS TECHNIQUE

When the user provides runtime logs as `.docx`:
```python
import zipfile, re
with zipfile.ZipFile("logs.docx", 'r') as z:
    text = re.sub(r'<[^>]+>', ' ', z.read('word/document.xml').decode('utf-8', errors='replace'))
    text = re.sub(r'\s+', ' ', text)
```

### Key indicators to check:
- **Skills resolved at startup:** Count of `Resolving skill "X"` lines → confirms which ChildSkills loaded
- **SummarizeCompliance `$top` value:** `$top=5` = V11, `$top=50` = old V3
- **GetBuiltInPolicyDefinition calls:** >0 means V11 is running, 0 means old agent
- **ListPolicyExemptions calls:** >0 means V11 is running
- **PolicyDefinitionNotFound count:** Shows how many BuiltIn policies weren't found

---

## 13. IMMEDIATE NEXT STEPS

1. **Resolve the platform-level "Check your plugins" error:**
   - Option A: Create agent manually in Security Copilot UI → export YAML → adapt
   - Option B: Check Microsoft documentation for new required manifest fields
   - Option C: Contact Microsoft support / check for known platform issues

2. **Once plugin binding works again:**
   - Deploy V11-lite first (7 ChildSkills, proven compatibility)
   - Verify output matches V11 design (4 sections, not 7)
   - If successful, try V11 full (9 ChildSkills with V89 spec)

3. **Testing checklist for any new deployment:**
   - [ ] Plugin shows enabled under Custom in Manage sources
   - [ ] Agent Build page shows correct number of Tools
   - [ ] Runtime logs show correct number of skills resolved
   - [ ] SummarizeCompliance uses `$top=5` (not 50)
   - [ ] Output has "SECTION A - COMPLIANCE SCORE" (not "Executive Summary")
   - [ ] GetBuiltInPolicyDefinition is called (if using V88/V89)
   - [ ] ListPolicyExemptions is called (if using V89)
