# E2E Test RSA Keys

**These are TEST-ONLY keys.** They are used exclusively by the E2E test
suite to sign RS256 JWTs for the mock JWKS authentication flow.

They are NOT used in any production, staging, or development environment.
They are NOT secret — they exist only so the E2E test can generate tokens
that the backend validates against the mock JWKS endpoint.

- `private_key.pem` — signs JWTs in `e2e-test.sh`
- `jwks.json` — served by `mock_ai_server.py` at `/.well-known/jwks.json`

To regenerate (if needed):
```bash
cd backend && uv run python3 -c "
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import json, base64

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
pub = key.public_key().public_numbers()

with open('../scripts/e2e-keys/private_key.pem', 'w') as f:
    f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode())

def b64(n):
    return base64.urlsafe_b64encode(n.to_bytes((n.bit_length()+7)//8, 'big')).rstrip(b'=').decode()

with open('../scripts/e2e-keys/jwks.json', 'w') as f:
    json.dump({'keys': [{'kty':'RSA','kid':'e2e-test-key','use':'sig','alg':'RS256','n':b64(pub.n),'e':b64(pub.e)}]}, f, indent=2)
"
```
