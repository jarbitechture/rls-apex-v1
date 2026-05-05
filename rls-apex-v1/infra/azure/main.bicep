// ─────────────────────────────────────────────────────────────────
// RLS Apex v1 — Azure infrastructure (skeleton)
//
// Resources provisioned:
//   • Static Web App (apps/web/)
//   • Key Vault (kv-rls-apex)
//   • App Insights (LLM tracing escape hatch; primary trace store
//     is Phoenix on bcc-db-llm01)
//
// NOT provisioned (residency rule per D-007):
//   • Azure Database for PostgreSQL (state lives on bcc-db-llm01)
//   • Azure Storage for documents (MinIO on bcc-db-llm01)
//
// Deploy:
//   az deployment group create -g rg-rls-apex \
//     --template-file infra/azure/main.bicep \
//     --parameters env=prod
// ─────────────────────────────────────────────────────────────────

param location string = resourceGroup().location
param env string = 'prod'
param tenantId string

var prefix = 'rls-apex-${env}'

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-rls-apex'
  location: location
  properties: {
    tenantId: tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    publicNetworkAccess: 'Disabled'  // private endpoint only
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
  }
}

resource swa 'Microsoft.Web/staticSites@2023-12-01' = {
  name: '${prefix}-web'
  location: location
  sku: { name: 'Standard', tier: 'Standard' }
  properties: {
    // Custom domain rls.mymanatee.org wired post-DNS-cutover
    repositoryUrl: 'https://github.com/jarbitechture/rls-apex-v1'
    branch: 'main'
    buildProperties: {
      appLocation: 'apps/web'
      outputLocation: 'dist'
    }
  }
}

resource ai 'Microsoft.Insights/components@2020-02-02' = {
  name: '${prefix}-ai'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    publicNetworkAccessForIngestion: 'Disabled'
  }
}

output kvName string = kv.name
output swaHostname string = swa.properties.defaultHostname
output appInsightsConnectionString string = ai.properties.ConnectionString
