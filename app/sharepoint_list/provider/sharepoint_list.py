from __future__ import annotations

import secrets
import time
import urllib.parse
from collections.abc import Mapping
from typing import Any

import requests
from dify_plugin import ToolProvider
from dify_plugin.entities.oauth import ToolOAuthCredentials
from dify_plugin.errors.tool import ToolProviderCredentialValidationError
from werkzeug import Request


class SharePointListProvider(ToolProvider):
    _API_BASE_URL = "https://graph.microsoft.com/v1.0"
    _SCOPES = "openid offline_access User.Read Sites.ReadWrite.All"

    def _validate_credentials(self, credentials: Mapping[str, Any]) -> None:
        # Optional: could call /me to validate, but keep lightweight here.
        if "access_token" not in credentials:
            raise ToolProviderCredentialValidationError("Missing access_token")

    def _get_oauth_endpoints(
        self, system_credentials: Mapping[str, Any]
    ) -> dict[str, str]:
        tenant_raw = system_credentials.get("tenant_id") or "common"
        tenant = str(tenant_raw).strip() or "common"
        base = (
            f"https://login.microsoftonline.com/"
            f"{urllib.parse.quote(tenant)}/oauth2/v2.0"
        )
        return {
            "tenant": tenant,
            "auth_url": f"{base}/authorize",
            "token_url": f"{base}/token",
        }

    def _oauth_get_authorization_url(
        self, redirect_uri: str, system_credentials: Mapping[str, Any]
    ) -> str:
        client_id = system_credentials.get("client_id")
        client_secret = system_credentials.get("client_secret")
        if not client_id or not client_secret:
            raise ToolProviderCredentialValidationError(
                "client_id and client_secret are required"
            )

        endpoints = self._get_oauth_endpoints(system_credentials)
        state = secrets.token_urlsafe(16)
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": self._SCOPES,
            "state": state,
            "response_mode": "query",
        }
        auth_url = f"{endpoints['auth_url']}?{urllib.parse.urlencode(params)}"

        return auth_url

    def _oauth_get_credentials(
        self,
        redirect_uri: str,
        system_credentials: Mapping[str, Any],
        request: Request,
    ) -> ToolOAuthCredentials:
        code = request.args.get("code")
        endpoints = self._get_oauth_endpoints(system_credentials)

        if not code:
            raise ToolProviderCredentialValidationError(
                "Authorization code is missing"
            )

        client_id = system_credentials.get("client_id")
        client_secret = system_credentials.get("client_secret")
        if not client_id or not client_secret:
            raise ToolProviderCredentialValidationError(
                "client_id and client_secret are required"
            )

        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "scope": self._SCOPES,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        response = requests.post(
            endpoints["token_url"],
            data=token_data,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token.strip():
            raise ToolProviderCredentialValidationError(
                "Failed to obtain access_token"
            )
        access_token = access_token.strip()

        refresh_token = payload.get("refresh_token")
        refresh_token = (
            refresh_token.strip()
            if isinstance(refresh_token, str)
            else refresh_token
        )
        expires_in = payload.get("expires_in", 3600)
        expires_at = int(time.time()) + int(expires_in)

        user_name, user_email, user_picture = self._fetch_userinfo(
            access_token
        )

        credentials = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": payload.get("token_type", "Bearer"),
            # Dify 側は値を encode して保存するため文字列に揃える
            "expires_at": str(expires_at),
            "user_email": user_email,
        }

        return ToolOAuthCredentials(
            credentials=credentials,
            expires_at=expires_at,
            name=user_name or user_email,
            avatar_url=user_picture,
        )

    def _oauth_refresh_credentials(
        self,
        redirect_uri: str,
        system_credentials: Mapping[str, Any],
        credentials: Mapping[str, Any],
    ) -> ToolOAuthCredentials:
        refresh_token = credentials.get("refresh_token")
        if not refresh_token:
            raise ToolProviderCredentialValidationError(
                "Refresh token not available"
            )

        client_id = system_credentials.get("client_id")
        client_secret = system_credentials.get("client_secret")
        if not client_id or not client_secret:
            raise ToolProviderCredentialValidationError(
                "client_id and client_secret are required"
            )

        endpoints = self._get_oauth_endpoints(system_credentials)

        token_data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": self._SCOPES,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        response = requests.post(
            endpoints["token_url"],
            data=token_data,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token.strip():
            raise ToolProviderCredentialValidationError(
                "Failed to refresh access_token"
            )
        access_token = access_token.strip()

        new_refresh_token = payload.get("refresh_token", refresh_token)
        new_refresh_token = (
            new_refresh_token.strip()
            if isinstance(new_refresh_token, str)
            else new_refresh_token
        )
        expires_in = payload.get("expires_in", 3600)
        expires_at = int(time.time()) + int(expires_in)

        user_name, user_email, user_picture = self._fetch_userinfo(
            access_token
        )

        updated_credentials = {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": payload.get("token_type", "Bearer"),
            # Dify 側は値を encode して保存するため文字列に揃える
            "expires_at": str(expires_at),
            "user_email": user_email,
        }

        return ToolOAuthCredentials(
            credentials=updated_credentials,
            expires_at=expires_at,
            name=user_name or user_email,
            avatar_url=user_picture,
        )

    def _fetch_userinfo(
        self, access_token: str
    ) -> tuple[str | None, str | None, str | None]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        try:
            resp = requests.get(
                f"{self._API_BASE_URL}/me", headers=headers, timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            name = data.get("displayName")
            email = data.get("mail") or data.get("userPrincipalName")
            picture = (
                data.get("photo", {}).get("@odata.mediaReadLink")
                if data.get("photo")
                else None
            )
            return name, email, picture
        except requests.RequestException as exc:
            raise ToolProviderCredentialValidationError(
                f"Failed to fetch user info: {exc}"
            ) from exc
