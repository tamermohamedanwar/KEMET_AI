from pathlib import Path
p=Path("/data/data/com.termux/files/home/products/Kemet_AI/app/services/social_connection_service.py")
s=p.read_text()
old='''        data = response.json()
        if not isinstance(data, dict) or not data.get("access_token"):
            raise ValueError("oauth_token_exchange_failed")
        return data
'''
new='''        data = response.json()
        if not isinstance(data, dict) or not data.get("access_token"):
            raise ValueError("oauth_token_exchange_failed")
        if spec.provider == "google":
            if not data.get("refresh_token"):
                data["refresh_token_missing_at_exchange"] = True
            data["oauth_exchange_verified"] = True
        return data
'''
if old not in s:
    raise SystemExit("TARGET_NOT_FOUND")
p.write_text(s.replace(old,new))
print("PATCH_APPLIED")
