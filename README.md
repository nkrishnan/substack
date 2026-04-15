# substack

A composable toolkit for scraping and analysing [Substack](https://substack.com) publications.

Substack does not have a public API, so this tool uses the unofficial JSON endpoints
that power the Substack web application.  The core idea is a set of rich data
structures (`Publication`, `PostCollection`, `CommentCollection`, `UserCollection`)
that you can filter, sort, and export in any combination — then use with any tool
you like: pandas, jq, R, Excel, …

## Installation

```bash
pip install .
# development / testing:
pip install -e ".[dev]"
```

---

## Python library — query the object model directly

This is the primary interface.  Load a publication once, then chain queries
freely:

```python
from substack import Publication

pub = Publication.load("https://example.substack.com")
```

### Posts

```python
pub.posts                                   # PostCollection (all posts)
pub.posts.of_type("newsletter")             # filter by post type
pub.posts.containing("Mailbag")             # title/subtitle contains text
pub.posts.since(datetime(2024, 1, 1, tzinfo=timezone.utc))
pub.posts.sorted_by("published_at", reverse=True)
pub.posts.most_discussed(10)                # top 10 by comment count
```

### Comments

```python
pub.comments                                # CommentCollection (all comments, all posts)
pub.posts.containing("Mailbag").comments   # comments on mailbag posts only

cc = pub.comments
cc.by_user("alice")                         # only Alice's comments
cc.top_level()                              # no replies
cc.min_likes(5)                             # at least 5 likes
cc.since(datetime(2024, 6, 1, tzinfo=timezone.utc))
cc.sorted_by("created_at")                 # earliest first
cc.sorted_by("like_count", reverse=True)   # most liked first
cc.most_liked(10)                           # top 10 liked
cc.where(lambda c: "mailbag" in c.body.lower())   # arbitrary predicate
```

### Analysis

```python
# Who comments most?
for user, count in pub.comments.top_commenters(n=20):
    print(user.handle, count)

# Chains are composable
pub.posts.containing("Mailbag") \
         .comments \
         .top_level() \
         .sorted_by("like_count", reverse=True)
```

### Export

Every collection exports to CSV or JSON:

```python
pub.comments.to_csv("comments.csv")         # write to file
pub.posts.to_json("posts.json")
text = pub.comments.to_json()               # or get the string
```

---

## Example: mailbag pattern analysis

*Does the author pick questions that arrived early, or ones with the most votes?*

```python
from substack import Publication
from datetime import datetime, timezone

pub = Publication.load(
    "https://example.substack.com",
    cache_dir="~/.cache/substack",   # avoid re-fetching on repeated runs
)

for post in pub.posts.containing("Mailbag").sorted_by("published_at"):
    cc = post.comments.top_level()
    print(f"\n── {post.title}  ({len(cc)} questions) ──")
    print("  Earliest 5:")
    for c in cc.sorted_by("created_at")[:5]:
        print(f"    {c.created_at:%Y-%m-%d %H:%M}  ❤{c.like_count:>4}  {c.body[:60]}")
    print("  Most-liked 5:")
    for c in cc.most_liked(5):
        print(f"    ❤{c.like_count:>4}  {c.created_at:%Y-%m-%d %H:%M}  {c.body[:60]}")
```

Or export to CSV and analyse in pandas:

```python
pub.posts.containing("Mailbag").comments.top_level().to_csv("mailbag_questions.csv")
```

```python
import pandas as pd
df = pd.read_csv("mailbag_questions.csv", parse_dates=["created_at"])
df["rank_by_time"]  = df["created_at"].rank()
df["rank_by_votes"] = df["like_count"].rank(ascending=False)
print(df[["rank_by_time", "rank_by_votes"]].corr())
```

---

## CLI — download and export data

The CLI is a thin layer on top of the same object model.  Its purpose is to
download data and surface it in standard formats so you can pipe into any tool.

```
substack [OPTIONS] COMMAND [ARGS]...

Options:
  --cookie SID                 substack.sid browser cookie (or set SUBSTACK_SID)
  --output [table|json|csv]    default: table
  --cache-dir PATH             cache API responses on disk (or set SUBSTACK_CACHE_DIR)
  --version / --help

Commands:
  posts           All posts (title, type, date, comment count, …)
  comments        All comments (author, timestamp, likes, body, …)
  comment-likes   Users who liked a specific comment
```

### Examples

```bash
# All posts as a table
substack posts https://example.substack.com

# Export all comments to CSV (cache so re-runs are instant)
substack --cache-dir ~/.cache/substack \
         --output csv \
         comments https://example.substack.com > comments.csv

# Who liked comment 12345678?
substack comment-likes https://example.substack.com --comment-id 12345678

# Pipe JSON into jq — e.g. find the 5 most-liked comments
substack --output json comments https://example.substack.com \
  | jq 'sort_by(-.like_count) | .[:5]'
```

### Authentication

Most public data does not need a login.  For private / paywalled content:

```bash
export SUBSTACK_SID="<value of substack.sid cookie from your browser>"
substack comments https://example.substack.com --output csv
```

---

## Architecture

```
substack/
├── models.py       User, Post, Comment, Like — plain dataclasses with datetime fields
├── publication.py  Publication, PostCollection, CommentCollection, UserCollection
│                   — rich queryable wrappers; all analysis lives here
├── client.py       Thin HTTP wrapper (requests + rate-limiting + auth)
├── scraper.py      Fetch raw API responses → model objects; cache-aware
├── cache.py        File-based JSON cache (opt-in)
└── cli.py          Click commands: posts / comments / comment-likes
```

## Development

```bash
pip install -e ".[dev]"
pytest
```
