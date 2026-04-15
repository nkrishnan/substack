"""Command-line interface for the Substack toolkit.

The CLI is a thin data-export layer on top of the :class:`~substack.publication.Publication`
object model.  Its purpose is to download and surface raw data so you can pipe
it into any analysis tool (jq, pandas, Excel, R, …).

Usage examples
--------------
# Export every post as CSV
substack posts https://example.substack.com --output csv > posts.csv

# Export all comments as JSON (includes timestamps and like counts)
substack comments https://example.substack.com --output json > comments.json

# Cache the responses locally so subsequent calls are instant
substack --cache-dir ~/.cache/substack comments https://example.substack.com --output csv

# Who liked comment 12345678?
substack comment-likes https://example.substack.com --comment-id 12345678

Pass --cookie (or set SUBSTACK_SID) for authenticated / paywalled content.

For custom analysis, use the Python library directly:

    from substack import Publication
    pub = Publication.load("https://example.substack.com")
    pub.posts.containing("Mailbag").comments.sorted_by("created_at").to_csv("mailbag.csv")
"""

from __future__ import annotations

import csv
import io
import json
import sys

import click

from .publication import Publication
from .scraper import fetch_comment_likes


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
    type=click.Choice(["table", "json", "csv"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--cache-dir",
    envvar="SUBSTACK_CACHE_DIR",
    default=None,
    metavar="PATH",
    help=(
        "Directory to cache downloaded API responses.  Re-running with the "
        "same directory reads from disk instead of hitting the network.  "
        "Can also be set via SUBSTACK_CACHE_DIR."
    ),
)
@click.pass_context
def main(
    ctx: click.Context, cookie: str | None, output: str, cache_dir: str | None
) -> None:
    """Substack scraping and analytics toolkit.

    Downloads data from a Substack publication and outputs it in the chosen
    format so it can be piped into any analysis tool.

    \b
    Quick start:
      substack posts  https://example.substack.com --output csv > posts.csv
      substack comments https://example.substack.com --output csv > comments.csv
    """
    ctx.ensure_object(dict)
    ctx.obj["cookie"] = cookie
    ctx.obj["output"] = output.lower()
    ctx.obj["cache_dir"] = cache_dir


# ---------------------------------------------------------------------------
# posts
# ---------------------------------------------------------------------------


@main.command("posts")
@click.argument("publication_url")
@click.option(
    "--no-comments",
    is_flag=True,
    default=False,
    help="Skip fetching comments (faster — only post metadata is downloaded).",
)
@click.pass_context
def posts_cmd(ctx: click.Context, publication_url: str, no_comments: bool) -> None:
    """List all posts for PUBLICATION_URL.

    Outputs id, title, type, subtitle, published_at, comment_count, and
    reaction_count for every post.
    """
    cookie: str | None = ctx.obj["cookie"]
    output: str = ctx.obj["output"]
    cache_dir: str | None = ctx.obj["cache_dir"]

    click.echo(f"Fetching posts from {publication_url} …", err=True)
    pub = Publication.load(
        publication_url,
        cookie=cookie,
        cache_dir=cache_dir,
        with_comments=False,
    )
    pc = pub.posts

    if output == "json":
        click.echo(pc.to_json())
    elif output == "csv":
        click.echo(pc.to_csv(), nl=False)
    else:
        _print_posts_table(pc)


def _print_posts_table(pc) -> None:
    if not len(pc):
        click.echo("No posts found.")
        return
    click.echo(
        f"\n{'ID':<12}{'Type':<14}{'Comments':>10}{'Likes':>8}  "
        f"{'Published':<22}{'Title'}"
    )
    click.echo("-" * 100)
    for p in pc.sorted_by("published_at", reverse=True):
        pub_str = p.published_at.strftime("%Y-%m-%d") if p.published_at else "—"
        title = p.title[:50] + ("…" if len(p.title) > 50 else "")
        click.echo(
            f"{p.id:<12}{p.post_type:<14}{p.comment_count:>10}{p.reaction_count:>8}"
            f"  {pub_str:<22}{title}"
        )


# ---------------------------------------------------------------------------
# comments
# ---------------------------------------------------------------------------


@main.command("comments")
@click.argument("publication_url")
@click.pass_context
def comments_cmd(ctx: click.Context, publication_url: str) -> None:
    """List all comments for PUBLICATION_URL.

    Outputs id, post, author, created_at, like_count, parent_id, and body
    for every comment across every post.  Use --output csv or --output json
    to consume the data with pandas, jq, or any other tool.
    """
    cookie: str | None = ctx.obj["cookie"]
    output: str = ctx.obj["output"]
    cache_dir: str | None = ctx.obj["cache_dir"]

    click.echo(f"Fetching all comments from {publication_url} …", err=True)
    pub = Publication.load(
        publication_url,
        cookie=cookie,
        cache_dir=cache_dir,
        with_comments=True,
    )
    cc = pub.comments

    if output == "json":
        click.echo(cc.to_json())
    elif output == "csv":
        click.echo(cc.to_csv(), nl=False)
    else:
        _print_comments_table(cc)


def _print_comments_table(cc) -> None:
    if not len(cc):
        click.echo("No comments found.")
        return
    click.echo(
        f"\n{'ID':<12}{'Author':<22}{'Likes':>6}  {'Created':<22}{'Post / Body preview'}"
    )
    click.echo("-" * 110)
    for c in cc:
        ts = c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else "—"
        preview = c.body[:50].replace("\n", " ") + ("…" if len(c.body) > 50 else "")
        context = f"[{c.post_title[:25]}] {preview}"
        click.echo(
            f"{c.id:<12}{c.author.handle:<22}{c.like_count:>6}  {ts:<22}{context}"
        )


# ---------------------------------------------------------------------------
# comment-likes
# ---------------------------------------------------------------------------


@main.command("comment-likes")
@click.argument("publication_url")
@click.option(
    "--comment-id",
    required=True,
    type=int,
    help="Numeric ID of the comment to inspect.",
)
@click.pass_context
def comment_likes_cmd(
    ctx: click.Context, publication_url: str, comment_id: int
) -> None:
    """Show users who liked COMMENT_ID on PUBLICATION_URL."""
    from .client import SubstackClient
    from .cache import Cache

    cookie: str | None = ctx.obj["cookie"]
    output: str = ctx.obj["output"]
    cache_dir: str | None = ctx.obj["cache_dir"]

    click.echo(
        f"Fetching likes for comment {comment_id} on {publication_url} …", err=True
    )
    client = SubstackClient(session_cookie=cookie)
    cache = Cache(cache_dir) if cache_dir else None
    likes = fetch_comment_likes(client, publication_url, comment_id, cache=cache)

    if output == "json":
        click.echo(
            json.dumps(
                [
                    {"handle": lk.user.handle, "name": lk.user.name}
                    for lk in likes
                ],
                indent=2,
            )
        )
    elif output == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["handle", "name"])
        for lk in likes:
            writer.writerow([lk.user.handle, lk.user.name])
        click.echo(buf.getvalue(), nl=False)
    else:
        if not likes:
            click.echo("No likes found.")
            return
        click.echo(f"\nComment {comment_id} — {len(likes)} like(s):\n")
        for lk in likes:
            name_part = f" ({lk.user.name})" if lk.user.name else ""
            click.echo(f"  @{lk.user.handle}{name_part}")
