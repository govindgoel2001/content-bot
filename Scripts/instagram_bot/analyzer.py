"""Stage 3 — Analyze & Generate: uses Claude to explain why each video worked
and generate 5 spin variations tailored to @gobi_automates."""

import anthropic

from config import ANTHROPIC_API_KEY, MY_HANDLE, SPIN_COUNT

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_SYSTEM = f"""\
You are an expert Instagram content strategist specializing in automation, \
AI tools, and productivity niches. You analyze competitor viral content and \
generate actionable content ideas for the creator @{MY_HANDLE}, whose brand \
focuses on automation workflows and AI productivity tools.

When analyzing a video, be specific, not generic. Reference the actual caption, \
hashtags, and metrics provided. Keep analysis tight and practical."""

_ANALYSIS_PROMPT = """\
Analyze this Instagram video that went viral:

Account: @{username}
Views: {views:,}
Likes: {likes:,}
Comments: {comments:,}
Engagement Rate: {engagement_rate}%
Caption: {caption}
Hashtags: {hashtags}
Posted: {posted_at}
URL: {url}

Your response MUST use this exact format with these section headers:

## Why It Worked
[Write 4-6 bullet points covering: hook strategy, content format, emotional trigger, \
hashtag/algorithm play, posting timing, and any trend or pattern it tapped into. \
Each bullet should be one sharp sentence.]

## Key Patterns to Steal
[Write 3 bullet points: the single most replicable tactic from this video that \
@{my_handle} can use immediately. Be specific — name the exact format, structure, \
or technique.]

## Spin 1: [Short punchy title]
**Format:** [Reel / Carousel / Story]
**Hook:** [Opening line — first 3 seconds]
**Angle:** [How this spins the original idea for the automation/AI niche]
**CTA:** [Call to action]

## Spin 2: [Short punchy title]
**Format:** [Reel / Carousel / Story]
**Hook:** [Opening line — first 3 seconds]
**Angle:** [Different angle — opposite viewpoint, niche down, or flip the format]
**CTA:** [Call to action]

## Spin 3: [Short punchy title]
**Format:** [Reel / Carousel / Story]
**Hook:** [Opening line — first 3 seconds]
**Angle:** [Trend-jacking or cultural reference adapted for automation niche]
**CTA:** [Call to action]

## Spin 4: [Short punchy title]
**Format:** [Reel / Carousel / Story]
**Hook:** [Opening line — first 3 seconds]
**Angle:** [Personal story / behind-the-scenes take for @{my_handle}]
**CTA:** [Call to action]

## Spin 5: [Short punchy title]
**Format:** [Reel / Carousel / Story]
**Hook:** [Opening line — first 3 seconds]
**Angle:** [Collab bait / duet / response format that drives shares]
**CTA:** [Call to action]"""


def analyze_post(post: dict) -> dict:
    """Run Claude analysis on a single normalized post. Returns post + analysis."""
    print(f"[Analyzer] Analyzing @{post['username']} — {post['views']:,} views")

    prompt = _ANALYSIS_PROMPT.format(
        my_handle=MY_HANDLE,
        **post,
    )

    message = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text
    sections = _parse_sections(raw)

    return {
        **post,
        "why_it_worked": sections.get("why_it_worked", raw),
        "key_patterns": sections.get("key_patterns", ""),
        "spin_1": sections.get("spin_1", ""),
        "spin_2": sections.get("spin_2", ""),
        "spin_3": sections.get("spin_3", ""),
        "spin_4": sections.get("spin_4", ""),
        "spin_5": sections.get("spin_5", ""),
        "full_analysis": raw,
    }


def _parse_sections(text: str) -> dict[str, str]:
    """Split Claude's response into named sections."""
    import re

    sections: dict[str, str] = {}
    pattern = re.compile(r"^##\s+(.+)$", re.MULTILINE)
    headers = list(pattern.finditer(text))

    for i, match in enumerate(headers):
        header = match.group(1).strip()
        start = match.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        content = text[start:end].strip()

        key = _header_to_key(header)
        sections[key] = content

    return sections


def _header_to_key(header: str) -> str:
    import re
    slug = re.sub(r"[^a-z0-9]+", "_", header.lower()).strip("_")
    # Map spin headers (Spin 1: ...) to spin_1 etc.
    m = re.match(r"spin_(\d+)", slug)
    if m:
        return f"spin_{m.group(1)}"
    return slug


def analyze_all(posts: list[dict]) -> list[dict]:
    return [analyze_post(p) for p in posts]
