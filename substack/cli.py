"""Command-line interface for the Substack toolkit.

Usage examples
--------------
# List the 20 most frequent commenters on a publication
substack top-commenters https://example.substack.com --top 20

# Show the most-liked posts' comments on a publication
substack most-liked-comments https://example.substack.com

# Show all comments by a specific user on a publication
substack user-comments https://example.substack.com --user someperson

# Show who liked a specific comment
substack comment-likers https://example.substack.com --comment-id 12345678

Pass --cookie if you need authenticated access (the value of the
substack.sid browser cookie).
"""

from __future__ import annotations

import json
import sys

import click

from .analysis import (
    CommentFrequency,
    LikeFrequency,
    comments_by_user,
    most_liked_comments,
    top_commenters,
    top_likers,
)
from .client import SubstackClient
from .scraper import (
    fetch_all_comments,
    fetch_comment_likes,
    fetch_user_comments,
)


# ---------------------------------------------------------------------------
# Shared options / group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option()
@click.option(
    "--cookie",
    envvar="SUBSTACK_SID",
    default=None,
    metavar="SID",
    help=(
        "Value of the substack.sid browser cookie for authenticated requests. "
        "Can also be set via the SUBSTACK_SID environment variable."
    ),
)
@click.option(
    "--output",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    show_default=True,
    help="Output format.",
)
@click.pass_context
def main(ctx: click.Context, cookie: str | None, output: str) -> None:
    """Substack scraping and analytics toolkit."""
    ctx.ensure_object(dict)
    ctx.obj["client"] = SubstackClient(session_cookie=cookie)
    ctx.obj["output"] = output.lower()


# ---------------------------------------------------------------------------
# top-commenters
# ---------------------------------------------------------------------------


@main.command("top-commenters")
@click.argument("publication_url")
@click.option("--top", default=10, show_default=True, help="Number of results.")
@click.pass_context
def top_commenters_cmd(ctx: click.Context, publication_url: str, top: int) -> None:
    """Show the most frequent commenters on PUBLICATION_URL."""
    client: SubstackClient = ctx.obj["client"]
    output: str = ctx.obj["output"]

    click.echo(f"Fetching all comments from {publication_url} …", err=True)
    comments = fetch_all_comments(client, publication_url)
    results = top_commenters(comments, n=top)

    if output == "json":
        click.echo(json.dumps([r._asdict() for r in results], indent=2))
    else:
        if not results:
            click.echo("No comments found.")
            return
        click.echo(f"\n{'Rank':<6}{'Handle':<30}{'Name':<30}{'Comments':>10}")
        click.echo("-" * 76)
        for rank, freq in enumerate(results, 1):
            click.echo(
                f"{rank:<6}{freq.handle:<30}{freq.name:<30}{freq.count:>10}"
            )


# ---------------------------------------------------------------------------
# most-liked-comments
# ---------------------------------------------------------------------------


@main.command("most-liked-comments")
@click.argument("publication_url")
@click.option("--top", default=10, show_default=True, help="Number of results.")
@click.pass_context
def most_liked_comments_cmd(
    ctx: click.Context, publication_url: str, top: int
) -> None:
    """Show the most-liked comments on PUBLICATION_URL."""
    client: SubstackClient = ctx.obj["client"]
    output: str = ctx.obj["output"]

    click.echo(f"Fetching all comments from {publication_url} …", err=True)
    comments = fetch_all_comments(client, publication_url)
    results = most_liked_comments(comments, n=top)

    if output == "json":
        click.echo(
            json.dumps(
                [
                    {
                        "id": c.id,
                        "author": c.author.handle,
                        "like_count": c.like_count,
                        "post_title": c.post_title,
                        "post_url": c.post_url,
                        "body": c.body,
                    }
                    for c in results
                ],
                indent=2,
            )
        )
    else:
        if not results:
            click.echo("No comments found.")
            return
        for rank, comment in enumerate(results, 1):
            click.echo(
                f"\n#{rank}  ❤ {comment.like_count}  "
                f"by @{comment.author.handle}  —  {comment.post_title}"
            )
            click.echo(f"    {comment.post_url}")
            preview = comment.body[:200].replace("\n", " ")
            if len(comment.body) > 200:
                preview += "…"
            click.echo(f"    {preview}")


# ---------------------------------------------------------------------------
# user-comments
# ---------------------------------------------------------------------------


@main.command("user-comments")
@click.argument("publication_url")
@click.option(
    "--user",
    "user_handle",
    required=True,
    metavar="HANDLE",
    help="Substack handle of the user whose comments to retrieve.",
)
@click.pass_context
def user_comments_cmd(
    ctx: click.Context, publication_url: str, user_handle: str
) -> None:
    """List comments left by USER on PUBLICATION_URL."""
    client: SubstackClient = ctx.obj["client"]
    output: str = ctx.obj["output"]

    click.echo(
        f"Fetching comments by @{user_handle} from {publication_url} …", err=True
    )
    all_comments = fetch_all_comments(client, publication_url)
    results = comments_by_user(all_comments, user_handle)

    if output == "json":
        click.echo(
            json.dumps(
                [
                    {
                        "id": c.id,
                        "like_count": c.like_count,
                        "post_title": c.post_title,
                        "post_url": c.post_url,
                        "body": c.body,
                    }
                    for c in results
                ],
                indent=2,
            )
        )
    else:
        if not results:
            click.echo(f"No comments found for @{user_handle}.")
            return
        click.echo(
            f"\nFound {len(results)} comment(s) by @{user_handle}:\n"
        )
        for comment in results:
            click.echo(f"  Post : {comment.post_title}")
            click.echo(f"  URL  : {comment.post_url}")
            click.echo(f"  Likes: {comment.like_count}")
            preview = comment.body[:300].replace("\n", " ")
            if len(comment.body) > 300:
                preview += "…"
            click.echo(f"  Body : {preview}")
            click.echo()


# ---------------------------------------------------------------------------
# comment-likers
# ---------------------------------------------------------------------------


@main.command("comment-likers")
@click.argument("publication_url")
@click.option(
    "--comment-id",
    required=True,
    type=int,
    help="Numeric ID of the comment to inspect.",
)
@click.option("--top", default=50, show_default=True, help="Number of results.")
@click.pass_context
def comment_likers_cmd(
    ctx: click.Context, publication_url: str, comment_id: int, top: int
) -> None:
    """Show users who liked COMMENT_ID on PUBLICATION_URL."""
    client: SubstackClient = ctx.obj["client"]
    output: str = ctx.obj["output"]

    click.echo(
        f"Fetching likes for comment {comment_id} on {publication_url} …", err=True
    )
    likes = fetch_comment_likes(client, publication_url, comment_id)
    results = top_likers(likes, n=top)

    if output == "json":
        click.echo(json.dumps([r._asdict() for r in results], indent=2))
    else:
        if not likes:
            click.echo("No likes found.")
            return
        click.echo(f"\nComment {comment_id} has {len(likes)} like(s):\n")
        for liker in likes:
            name_part = f" ({liker.user.name})" if liker.user.name else ""
            click.echo(f"  @{liker.user.handle}{name_part}")
