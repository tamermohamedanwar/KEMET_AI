from pathlib import Path
p=Path("app/services/social_connection_service.py")
s=p.read_text()
old='''        token = self._exchange(spec, code)
        identity = self._verify_identity(spec, token)
        scopes = self._scopes(token, os.getenv(spec.scopes_env, ""))
        if not identity.get("account_ref") or not identity.get("publishing_capable"):
            raise ValueError("publishing_capability_not_verified")
        credential_ref = social_credential_store.put(int(organization_id), int(user_id), spec.channel, token)
'''
new='''        token = self._exchange(spec, code)
        if spec.provider == "google" and not token.get("refresh_token"):
            raise ValueError("oauth_refresh_token_missing")
        identity = self._verify_identity(spec, token)
        scopes = self._scopes(token, os.getenv(spec.scopes_env, ""))
        if not identity.get("account_ref") or not identity.get("publishing_capable"):
            raise ValueError("publishing_capability_not_verified")
        credential_ref = social_credential_store.put(int(organization_id), int(user_id), spec.channel, token)
'''
if old not in s:
    raise SystemExit("TARGET_NOT_FOUND")
p.write_text(s.replace(old,new,1))
print("CALLBACK_REFRESH_TOKEN_GATE_APPLIED")
