"""Toolset ``issue_inspect`` — Attachment content (vision + text), thumbnails, votes, remote links."""

import base64
import logging
import mimetypes
from collections.abc import Callable
from typing import Annotated, Any

from fastmcp import Context
from mcp.types import ImageContent, TextContent
from pydantic import Field

from ..client import JiraError
from ..util import error_json, get_client, seg, to_json

logger = logging.getLogger(__name__)

# Images are returned as MCP ImageContent; the model downsamples anything
# bigger anyway, so there is no point shipping more than a few MB.
_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_MAX_TEXT_DOWNLOAD_BYTES = 1_000_000
_MAX_TEXT_CHARS = 50_000
_MAX_BINARY_BASE64_BYTES = 200_000
_VISIBLE_IMAGE_MIMES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})
_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".tif", ".tiff")
_AMBIGUOUS_MIMES = frozenset({"", "application/octet-stream", "binary/octet-stream"})
_TEXT_MIME_PREFIXES = (
    "text/",
    "application/json",
    "application/xml",
    "application/javascript",
    "application/csv",
    "application/x-yaml",
    "application/sql",
)
_TEXT_EXTENSIONS = (
    ".txt",
    ".csv",
    ".json",
    ".xml",
    ".yml",
    ".yaml",
    ".md",
    ".log",
    ".sql",
    ".groovy",
    ".py",
    ".js",
    ".ts",
    ".java",
    ".kt",
    ".sh",
)


def is_image_attachment(mime: str, filename: str) -> tuple[bool, str]:
    """Return ``(is_image, resolved_mime)``, trusting the extension when the MIME is vague."""
    mime = (mime or "").lower()
    if mime.startswith("image/"):
        return True, mime
    if mime in _AMBIGUOUS_MIMES and filename.lower().endswith(_IMAGE_EXTENSIONS):
        return True, mimetypes.guess_type(filename)[0] or "image/png"
    return False, mime or "application/octet-stream"


def looks_like_text(mime: str, filename: str) -> bool:
    if mime and mime.startswith(_TEXT_MIME_PREFIXES):
        return True
    return filename.lower().endswith(_TEXT_EXTENSIONS)


async def _check_owner(client: Any, issue_key: str, attachment_id: str) -> str | None:
    """Confirm the attachment belongs to ``issue_key``.

    Reading the issue's attachment list is also what releases the
    attachment when the issue guard is on.
    """
    if not issue_key:
        return None
    data = await client.rest_get(f"/rest/api/2/issue/{seg(issue_key)}", fields="attachment")
    attachments = (data.get("fields") or {}).get("attachment") or []
    if str(attachment_id).strip() not in {str(a.get("id")) for a in attachments}:
        return error_json(f"attachment {attachment_id} does not belong to {issue_key}", status=404)
    return None


_ISSUE_KEY_FIELD = Field(
    description=(
        "Issue the attachment belongs to, e.g. 'HR-123'. Verifies ownership; "
        "required when the server runs with the issue guard."
    )
)


def register(tool: Callable[..., Any]) -> None:  # noqa: C901 — flat list of thin wrappers
    # =====================================================================
    # Issue deep-inspection — votes, remote links, attachment content
    # =====================================================================

    @tool(
        tags={"read", "toolset:issue_inspect"},
        annotations={"title": "Get Issue Votes", "readOnlyHint": True},
    )
    async def get_issue_votes(
        ctx: Context,
        issue_key: Annotated[str, Field(description="Issue key, e.g. 'HR-123'.")],
    ) -> str:
        """Total votes and (where visible) voter list for an issue.

        ``voters`` is populated only when the caller has the *View Voters
        and Watchers* project permission — an empty array does not imply
        no voters.
        """
        client = get_client(ctx)
        try:
            return to_json(await client.rest_get(f"/rest/api/2/issue/{seg(issue_key)}/votes"))
        except JiraError as exc:
            return error_json(f"get_issue_votes failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:issue_inspect"},
        annotations={"title": "Get Issue Remote Links", "readOnlyHint": True},
    )
    async def get_issue_remotelinks(
        ctx: Context,
        issue_key: Annotated[str, Field(description="Issue key.")],
        global_id: Annotated[
            str,
            Field(description="Optional global-id filter (matches a single link)."),
        ] = "",
    ) -> str:
        """External links attached to an issue — ``/rest/api/2/issue/{key}/remotelink``."""
        client = get_client(ctx)
        params: dict[str, Any] = {}
        if global_id:
            params["globalId"] = global_id
        try:
            return to_json(
                await client.rest_get(f"/rest/api/2/issue/{seg(issue_key)}/remotelink", **params)
            )
        except JiraError as exc:
            return error_json(f"get_issue_remotelinks failed: {exc}", status=exc.status)

    @tool(
        tags={"read", "toolset:issue_inspect"},
        annotations={"title": "Get Attachment Content", "readOnlyHint": True},
    )
    async def get_attachment_content(
        ctx: Context,
        attachment_id: Annotated[
            str, Field(description="Numeric attachment id (from the issue's fields.attachment).")
        ],
        issue_key: Annotated[str, _ISSUE_KEY_FIELD] = "",
    ) -> list[TextContent | ImageContent]:
        """Download an attachment and return it inline for analysis.

        Behaviour by MIME type:

        * **Image** (png/jpeg/gif/webp) up to 5 MB → MCP ImageContent that
          Claude can see natively (screenshots, diagrams, image logs).
        * **Text** (text/*, json, xml, csv, yaml, sql, md, common source
          extensions) → inlined UTF-8 text, truncated at 50 000 characters.
        * **Other binary** up to 200 KB → base64 blob inside a TextContent
          for programmatic use.
        * **Too large** → metadata + download URL so the caller can stream
          the file out-of-band.
        """
        client = get_client(ctx)
        mismatch = await _check_owner(client, issue_key, attachment_id)
        if mismatch:
            return [TextContent(type="text", text=mismatch)]
        try:
            meta = await client.rest_get(f"/rest/api/2/attachment/{seg(attachment_id)}")
        except JiraError as exc:
            return [
                TextContent(
                    type="text",
                    text=error_json(
                        f"get_attachment_content metadata failed: {exc}",
                        status=exc.status,
                    ),
                )
            ]
        filename: str = meta.get("filename", "") or ""
        size: int = int(meta.get("size") or 0)
        mime: str = (meta.get("mimeType") or "").lower()
        content_url: str = meta.get("content") or ""
        is_image, resolved_mime = is_image_attachment(mime, filename)
        visible_mime = resolved_mime in _VISIBLE_IMAGE_MIMES

        if is_image and size > _MAX_IMAGE_BYTES:
            return [
                TextContent(
                    type="text",
                    text=to_json(
                        {
                            "id": attachment_id,
                            "filename": filename,
                            "size": size,
                            "mimeType": resolved_mime,
                            "warning": (
                                f"Image too large ({size} > {_MAX_IMAGE_BYTES}). "
                                "Use get_attachment_thumbnail or the URL below."
                            ),
                            "contentUrl": content_url,
                        }
                    ),
                )
            ]
        if not is_image and size > _MAX_TEXT_DOWNLOAD_BYTES:
            return [
                TextContent(
                    type="text",
                    text=to_json(
                        {
                            "id": attachment_id,
                            "filename": filename,
                            "size": size,
                            "mimeType": resolved_mime,
                            "warning": (
                                f"File too large ({size} > "
                                f"{_MAX_TEXT_DOWNLOAD_BYTES}). Use the URL."
                            ),
                            "contentUrl": content_url,
                        }
                    ),
                )
            ]

        try:
            data = await client.fetch_bytes(
                content_url,
                max_bytes=_MAX_IMAGE_BYTES if is_image else _MAX_TEXT_DOWNLOAD_BYTES,
            )
        except JiraError as exc:
            return [
                TextContent(
                    type="text",
                    text=error_json(
                        f"attachment download failed: {exc}",
                        status=exc.status,
                        id=attachment_id,
                        filename=filename,
                    ),
                )
            ]

        if is_image and visible_mime:
            return [
                TextContent(
                    type="text",
                    text=to_json(
                        {
                            "id": attachment_id,
                            "filename": filename,
                            "size": size,
                            "mimeType": resolved_mime,
                        }
                    ),
                ),
                ImageContent(
                    type="image",
                    data=base64.b64encode(data).decode("ascii"),
                    mimeType=resolved_mime,
                ),
            ]
        if is_image:
            return [
                TextContent(
                    type="text",
                    text=to_json(
                        {
                            "id": attachment_id,
                            "filename": filename,
                            "size": size,
                            "mimeType": resolved_mime,
                            "hint": (
                                f"MIME {resolved_mime} is not natively rendered; returning base64."
                            ),
                            "contentBase64": base64.b64encode(data).decode("ascii"),
                        }
                    ),
                )
            ]

        if looks_like_text(resolved_mime, filename):
            try:
                text = data.decode("utf-8", errors="replace")
            except Exception:
                text = None
            if text is not None:
                return [
                    TextContent(
                        type="text",
                        text=to_json(
                            {
                                "id": attachment_id,
                                "filename": filename,
                                "mimeType": resolved_mime,
                                "content": text[:_MAX_TEXT_CHARS],
                                "truncated": len(text) > _MAX_TEXT_CHARS,
                                "originalLength": len(text),
                            }
                        ),
                    )
                ]

        if size <= _MAX_BINARY_BASE64_BYTES:
            return [
                TextContent(
                    type="text",
                    text=to_json(
                        {
                            "id": attachment_id,
                            "filename": filename,
                            "size": size,
                            "mimeType": resolved_mime,
                            "contentBase64": base64.b64encode(data).decode("ascii"),
                        }
                    ),
                )
            ]
        return [
            TextContent(
                type="text",
                text=to_json(
                    {
                        "id": attachment_id,
                        "filename": filename,
                        "size": size,
                        "mimeType": resolved_mime,
                        "hint": "Binary too large for inline base64. Use URL.",
                        "contentUrl": content_url,
                    }
                ),
            )
        ]

    @tool(
        tags={"read", "toolset:issue_inspect"},
        annotations={"title": "Get Attachment Thumbnail", "readOnlyHint": True},
    )
    async def get_attachment_thumbnail(
        ctx: Context,
        attachment_id: Annotated[str, Field(description="Numeric attachment id.")],
        issue_key: Annotated[str, _ISSUE_KEY_FIELD] = "",
    ) -> list[TextContent | ImageContent]:
        """Fetch the server-generated thumbnail for an image attachment.

        Cheaper than :func:`get_attachment_content` for large images — useful
        when scanning many attachments to find the right one. Falls back to a
        text-only metadata response when the server didn't generate a
        thumbnail (non-image, or generation failed).
        """
        client = get_client(ctx)
        mismatch = await _check_owner(client, issue_key, attachment_id)
        if mismatch:
            return [TextContent(type="text", text=mismatch)]
        try:
            meta = await client.rest_get(f"/rest/api/2/attachment/{seg(attachment_id)}")
        except JiraError as exc:
            return [
                TextContent(
                    type="text",
                    text=error_json(
                        f"get_attachment_thumbnail metadata failed: {exc}",
                        status=exc.status,
                    ),
                )
            ]
        thumb_url = meta.get("thumbnail")
        if not thumb_url:
            return [
                TextContent(
                    type="text",
                    text=to_json(
                        {
                            "id": attachment_id,
                            "filename": meta.get("filename"),
                            "mimeType": meta.get("mimeType"),
                            "error": (
                                "no thumbnail available (non-image, or server "
                                "did not generate one)."
                            ),
                        }
                    ),
                )
            ]
        try:
            data = await client.fetch_bytes(thumb_url, max_bytes=_MAX_IMAGE_BYTES)
        except JiraError as exc:
            return [
                TextContent(
                    type="text",
                    text=error_json(
                        f"thumbnail download failed: {exc}",
                        status=exc.status,
                    ),
                )
            ]
        return [
            TextContent(
                type="text",
                text=to_json(
                    {
                        "id": attachment_id,
                        "filename": meta.get("filename"),
                        "mimeType": meta.get("mimeType"),
                        "thumbnail": True,
                    }
                ),
            ),
            ImageContent(
                type="image",
                data=base64.b64encode(data).decode("ascii"),
                mimeType="image/png",
            ),
        ]
