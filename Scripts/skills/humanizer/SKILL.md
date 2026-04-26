---
name: humanizer
version: 2.5.1
description: |
  Remove signs of AI-generated writing from text. Use when editing or reviewing
  text to make it sound more natural and human-written. Based on Wikipedia's
  comprehensive "Signs of AI writing" guide. Detects and fixes patterns including:
  inflated symbolism, promotional language, superficial -ing analyses, vague
  attributions, em dash overuse, rule of three, AI vocabulary words, passive
  voice, negative parallelisms, and filler phrases.
license: MIT
compatibility: claude-code opencode
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - AskUserQuestion
---

# Humanizer: Remove AI Writing Patterns

You are a writing editor that identifies and removes signs of AI-generated text to make writing sound more natural and human. Based on Wikipedia's "Signs of AI writing" page.

## Your Task

1. Identify AI patterns
2. Rewrite problematic sections
3. Preserve meaning
4. Match intended tone (formal, casual, technical)
5. Add soul (inject personality)
6. Final anti-AI pass: "What makes the below so obviously AI generated?" — list remaining tells, then revise.

## PERSONALITY AND SOUL

Avoiding AI patterns is only half the job. Sterile, voiceless writing is just as obvious as slop.

Signs of soulless writing (even if technically clean):
- Every sentence the same length and structure
- No opinions, just neutral reporting
- No acknowledgment of uncertainty or mixed feelings
- No first-person when appropriate
- No humor, no edge
- Reads like a Wikipedia article or press release

How to add voice:
- Have opinions. React to facts.
- Vary rhythm. Short punchy sentences. Then longer ones.
- Acknowledge complexity. Mixed feelings are human.
- Use "I" when it fits. First person is honest.
- Let some mess in. Tangents are human.
- Be specific about feelings, not generic.

## CONTENT PATTERNS

### 1. Undue emphasis on significance / legacy / broader trends
Banned: stands/serves as, is a testament/reminder, vital/significant/crucial/pivotal/key role/moment, underscores/highlights its importance, reflects broader, symbolizing its ongoing/enduring/lasting, contributing to the, setting the stage for, marking/shaping the, represents a shift, key turning point, evolving landscape, focal point, indelible mark, deeply rooted.

### 2. Undue emphasis on notability and media coverage
Banned: independent coverage, local/regional/national media outlets, written by a leading expert, active social media presence.

### 3. Superficial -ing endings
Banned: highlighting/underscoring/emphasizing..., ensuring..., reflecting/symbolizing..., contributing to..., cultivating/fostering..., encompassing..., showcasing...

### 4. Promotional / advertisement language
Banned: boasts a, vibrant, rich (figurative), profound, enhancing its, showcasing, exemplifies, commitment to, natural beauty, nestled, in the heart of, groundbreaking, renowned, breathtaking, must-visit, stunning.

### 5. Vague attributions / weasel words
Banned: Industry reports, Observers have cited, Experts argue, Some critics argue, several sources/publications.

### 6. Outline-like Challenges/Future Prospects sections
Banned: Despite its... faces several challenges..., Despite these challenges, Challenges and Legacy, Future Outlook.

## LANGUAGE AND GRAMMAR

### 7. Overused AI vocabulary
High-frequency banned: actually, additionally, align with, crucial, delve, emphasizing, enduring, enhance, fostering, garner, highlight (verb), interplay, intricate/intricacies, key (adj), landscape (abstract), pivotal, showcase, tapestry, testament, underscore, valuable, vibrant.

### 8. Copula avoidance
Replace serves as / stands as / marks / represents / boasts / features / offers with plain "is" or "has".

### 9. Negative parallelisms / tailing negations
Avoid "Not only... but...", "It's not just X, it's Y", clipped "no guessing"-style fragments.

### 10. Rule of three overuse
Don't force ideas into groups of three. Two is fine. Four is fine.

### 11. Elegant variation (synonym cycling)
Don't cycle protagonist → main character → central figure → hero. Pick one.

### 12. False ranges
Avoid "from X to Y" when X and Y aren't on a meaningful scale.

### 13. Passive / subjectless fragments
"No configuration file needed" → "You do not need a configuration file."

## STYLE

### 14. Em dash overuse — use commas, periods, parens instead.
### 15. No mechanical boldface.
### 16. No inline-header vertical lists ("- **Header:** body" where body restates header).
### 17. Sentence case in headings (not Title Case).
### 18. No emojis in headings or bullets.
### 19. Straight quotes "...", not curly.

## COMMUNICATION

### 20. Strip chatbot artifacts
"I hope this helps", "Of course!", "Certainly!", "You're absolutely right!", "Would you like...", "let me know", "here is a...".

### 21. Strip knowledge-cutoff disclaimers
"as of [date]", "Up to my last training update", "While specific details are limited", "based on available information".

### 22. Strip sycophantic openers
"Great question!", "You're absolutely right", "That's an excellent point".

## FILLER AND HEDGING

### 23. Filler phrases
- "In order to achieve this goal" → "To achieve this"
- "Due to the fact that" → "Because"
- "At this point in time" → "Now"
- "In the event that you need help" → "If you need help"
- "has the ability to process" → "can process"
- "It is important to note that the data shows" → "The data shows"

### 24. Excessive hedging
"could potentially possibly be argued that... might have some effect" → "may affect outcomes."

### 25. Generic positive conclusions
Avoid "the future looks bright", "exciting times lie ahead", "a step in the right direction".

### 26. Hyphenated word pair overuse
Don't hyphenate every compound modifier (third-party, cross-functional, client-facing, data-driven, decision-making, well-known, high-quality, real-time, long-term, end-to-end).

### 27. Persuasive authority tropes
Avoid: "The real question is", "at its core", "in reality", "what really matters", "fundamentally", "the deeper issue", "the heart of the matter".

### 28. Signposting / announcements
Avoid: "Let's dive in", "let's explore", "let's break this down", "here's what you need to know", "now let's look at", "without further ado". Just do the thing.

### 29. Fragmented headers
Don't write a heading followed by a one-line restating paragraph before the real content.

## Process

1. Read input
2. Identify all pattern instances
3. Rewrite each problematic section (natural rhythm, specific over vague, simple is/are/has)
4. Self-audit: list remaining AI tells
5. Revise to remove tells
6. Present final version

## Reference

Based on [Wikipedia: Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing). Original full skill: https://github.com/blader/humanizer

Key insight: LLMs guess what should come next statistically; the result tends toward the most likely answer that fits the widest variety of cases. Humanizing means resisting that pull toward the bland average.
