# Test Fixtures

## TEST-ONLY — DO NOT USE IN PROD

`test_rsa.pem` and `test_rsa.pub` are an RS256 keypair generated solely for the
JWT-verify unit tests in `tests/test_mcp_jwt_verify.py`. They have no production
significance and must never be deployed.

In production, the gateway holds the private key in Azure Key Vault and the
tools read the public key from `MCP_GATEWAY_PUBLIC_KEY_PATH` (default
`/etc/rls-apex/gateway.pub`).

Regenerate via:

```
openssl genrsa -out tests/fixtures/test_rsa.pem 2048
openssl rsa -in tests/fixtures/test_rsa.pem -pubout -out tests/fixtures/test_rsa.pub
```
