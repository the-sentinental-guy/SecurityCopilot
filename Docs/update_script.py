import os

repo_dir = '/Users/yashmudaliar/GitHubRepo-VSCode/SecurityCopilot'
manifest_path = os.path.join(repo_dir, 'newManifestAzurePolicy86.yaml')
new_manifest_path = os.path.join(repo_dir, 'newManifestAzurePolicy87.yaml')
agent_path = os.path.join(repo_dir, 'AzurePolicyOptimizerAgent_Version2.yaml')
new_agent_path = os.path.join(repo_dir, 'AzurePolicyOptimizerAgent_Version3.yaml')

with open(manifest_path, 'r') as f:
    text = f.read()

# Insert the new path block
new_path_block = """
  /subscriptions/{subscriptionId}/providers/Microsoft.Authorization/policyDefinitions/{policyDefinitionName}:
    get:
      operationId: GetPolicyDefinition
      summary: Get a specific policy definition
      description: Retrieves the metadata for a single specific policy definition by its name. Use this to get the displayName and description of a policy when you already know its ID or Name, instead of listing all definitions.
      parameters:
        - name: subscriptionId
          in: path
          required: true
          schema:
            type: string
          description: The Azure Subscription ID.
        - name: policyDefinitionName
          in: path
          required: true
          schema:
            type: string
          description: The name of the policy definition to retrieve. If the policyDefinitionId is /providers/Microsoft.Authorization/policyDefinitions/1a2b3c, this value is 1a2b3c. Extract this from the policyDefinitionId.
        - name: api-version
          in: query
          required: true
          schema:
            type: string
            default: "2023-04-01"
      responses:
        "200":
          description: Success.
          content:
            application/json:
              schema:
                type: object
                properties:
                  id:
                    type: string
                  name:
                    type: string
                  properties:
                    type: object
                    properties:
                      displayName:
                        type: string
                      description:
                        type: string
                      policyType:
                        type: string
"""

if "operationId: GetPolicyDefinition" not in text:
    text = text.replace("  /subscriptions/{subscriptionId}/providers/Microsoft.Authorization/policyAssignments:", new_path_block.lstrip('\n') + "\n  /subscriptions/{subscriptionId}/providers/Microsoft.Authorization/policyAssignments:")

with open(new_manifest_path, 'w') as f:
    f.write(text)

with open(agent_path, 'r') as f:
    agent_text = f.read()

old_step3 = """            STEP 3 — Policy Definition Lookup:
            Call ListPolicyDefinitions once. Match ONLY definitions whose id appears in the non-compliant list from Step 1. Discard all others immediately.
            For each match, extract: properties.displayName, properties.description, properties.policyType (BuiltIn, Custom, Static).
            Category and effect are NOT sourced from this operation."""

new_step3 = """            STEP 3 — Policy Definition Lookup:
            For each unique non-compliant policyDefinitionId from Step 1, extract the policy definition name (the last segment of the ID).
            Call GetPolicyDefinition for each extracted name (batch max 5 at a time).
            For each match, extract: properties.displayName, properties.description, properties.policyType (BuiltIn, Custom, Static).
            Category and effect are NOT sourced from this operation."""

agent_text = agent_text.replace(old_step3, new_step3)
# Fix step 3 data source reference
agent_text = agent_text.replace("NAME, DESCRIPTION, TYPE from ListPolicyDefinitions (Step 3)", "NAME, DESCRIPTION, TYPE from GetPolicyDefinition (Step 3)")
agent_text = agent_text.replace("Intent source: displayName and description from ListPolicyDefinitions (Step 3).", "Intent source: displayName and description from GetPolicyDefinition (Step 3).")

if "- GetPolicyDefinition" not in agent_text:
    agent_text = agent_text.replace("- ListPolicyDefinitions\n", "- ListPolicyDefinitions\n          - GetPolicyDefinition\n")

agent_text = agent_text.replace("AzurePolicyOptimizerAgent", "AzurePolicyOptimizerAgentV3")
agent_text = agent_text.replace("Azure Policy Optimizer Agent", "Azure Policy Optimizer Agent V3")

with open(new_agent_path, 'w') as f:
    f.write(agent_text)

print(f"Created {new_manifest_path}")
print(f"Created {new_agent_path}")
