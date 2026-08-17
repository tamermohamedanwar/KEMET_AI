import os
import secrets
from urllib.parse import urlencode

import requests

from app import db
from app.models.user import User
from app.models.organization import Organization
from app.models.subscription import Subscription


def _get_or_create_user(
    provider,
    provider_id,
    email,
    full_name,
):
    if not email:
        raise ValueError("OAuth provider did not return an email")

    email = email.strip().lower()

    user = User.query.filter_by(
        oauth_provider=provider,
        oauth_id=str(provider_id),
    ).first()

    if user:
        return user

    user = User.query.filter_by(email=email).first()

    if user:
        user.oauth_provider = provider
        user.oauth_id = str(provider_id)
        db.session.commit()
        return user

    organization_name = f"{full_name}'s Organization"

    base_slug = email.split("@")[0].lower()
    slug = base_slug

    counter = 1

    while Organization.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    organization = Organization(
        name=organization_name,
        slug=slug,
    )

    db.session.add(organization)
    db.session.flush()

    subscription = Subscription(
        organization_id=organization.id,
        plan="free",
        status="active",
    )

    user = User(
        organization_id=organization.id,
        full_name=full_name or email.split("@")[0],
        email=email,
        password_hash=secrets.token_urlsafe(32),
        role="admin",
        oauth_provider=provider,
        oauth_id=str(provider_id),
    )

    db.session.add(subscription)
    db.session.add(user)
    db.session.commit()

    return user


def google_authorize_url():
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "").strip()

    if not client_id or not redirect_uri:
        raise RuntimeError("Google OAuth is not configured")

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }

    return (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        + urlencode(params)
    )


def google_login(code):
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "").strip()

    if not client_id or not client_secret or not redirect_uri:
        raise RuntimeError("Google OAuth is not configured")

    token_response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        timeout=15,
    )

    token_response.raise_for_status()

    token_data = token_response.json()

    access_token = token_data.get("access_token")

    if not access_token:
        raise RuntimeError("Google did not return an access token")

    user_response = requests.get(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        timeout=15,
    )

    user_response.raise_for_status()

    profile = user_response.json()

    provider_id = profile.get("sub")
    email = profile.get("email")
    full_name = profile.get("name") or email

    if not provider_id or not email:
        raise RuntimeError("Google profile is incomplete")

    return _get_or_create_user(
        "google",
        provider_id,
        email,
        full_name,
    )


def facebook_authorize_url():
    client_id = os.getenv("FACEBOOK_CLIENT_ID", "").strip()
    redirect_uri = os.getenv("FACEBOOK_REDIRECT_URI", "").strip()

    if not client_id or not redirect_uri:
        raise RuntimeError("Facebook OAuth is not configured")

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "email,public_profile",
    }

    return (
        "https://www.facebook.com/v23.0/dialog/oauth?"
        + urlencode(params)
    )


def facebook_login(code):
    client_id = os.getenv("FACEBOOK_CLIENT_ID", "").strip()
    client_secret = os.getenv("FACEBOOK_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("FACEBOOK_REDIRECT_URI", "").strip()

    if not client_id or not client_secret or not redirect_uri:
        raise RuntimeError("Facebook OAuth is not configured")

    token_response = requests.get(
        "https://graph.facebook.com/v23.0/oauth/access_token",
        params={
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=15,
    )

    token_response.raise_for_status()

    token_data = token_response.json()

    access_token = token_data.get("access_token")

    if not access_token:
        raise RuntimeError("Facebook did not return an access token")

    profile_response = requests.get(
        "https://graph.facebook.com/me",
        params={
            "fields": "id,name,email",
            "access_token": access_token,
        },
        timeout=15,
    )

    profile_response.raise_for_status()

    profile = profile_response.json()

    provider_id = profile.get("id")
    email = profile.get("email")
    full_name = profile.get("name") or "Kemet AI User"

    if not provider_id or not email:
        raise RuntimeError(
            "Facebook did not return an email. "
            "Make sure the email permission is enabled."
        )

    return _get_or_create_user(
        "facebook",
        provider_id,
        email,
        full_name,
    )
