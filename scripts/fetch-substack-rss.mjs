import { writeFile } from "node:fs/promises";

const FEED_URL = "https://nirantar.substack.com/feed";
const OUTPUT_FILE = "posts.json";
const MAX_POSTS = 6;

function decodeEntities(value = "") {
  return value
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'");
}

function getTag(block, tagName) {
  const pattern = new RegExp(`<${tagName}\\b[^>]*>([\\s\\S]*?)<\\/${tagName}>`, "i");
  const match = block.match(pattern);
  return match ? decodeEntities(match[1].trim()) : "";
}

function stripHtml(value = "") {
  return value
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function excerpt(value = "", maxLength = 190) {
  const text = stripHtml(decodeEntities(value))
    .replace(/Continue reading.*$/i, "")
    .replace(/Read more.*$/i, "")
    .trim();

  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 1).replace(/\s+\S*$/, "")}…`;
}

function dateLabel(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "The Still Signal";

  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
    timeZone: "UTC",
  });
}

function issueNumber(title = "", link = "") {
  const haystack = `${title} ${link}`;
  const match = haystack.match(/issue[-_\s#]*(\d+)/i);
  return match ? `Issue #${match[1].padStart(3, "0")}` : "";
}

const response = await fetch(FEED_URL, {
  headers: {
    "user-agent": "nirantar-rss-fetcher/1.0",
    "accept": "application/rss+xml, application/xml, text/xml",
  },
});

if (!response.ok) {
  throw new Error(`Failed to fetch RSS feed: ${response.status} ${response.statusText}`);
}

const xml = await response.text();
const itemBlocks = Array.from(xml.matchAll(/<item\b[\s\S]*?<\/item>/gi)).map((match) => match[0]);

const posts = itemBlocks
  .slice(0, MAX_POSTS)
  .map((item) => {
    const title = stripHtml(getTag(item, "title"));
    const link = stripHtml(getTag(item, "link"));
    const pubDateRaw = stripHtml(getTag(item, "pubDate"));
    const descriptionRaw = getTag(item, "description") || getTag(item, "content:encoded");
    const issue = issueNumber(title, link);
    const date = dateLabel(pubDateRaw);

    return {
      title,
      link,
      pubDate: pubDateRaw ? new Date(pubDateRaw).toISOString() : "",
      dateLabel: issue ? `${issue} · ${date}` : date,
      description: excerpt(descriptionRaw),
    };
  })
  .filter((post) => post.title && post.link);

const payload = {
  source: FEED_URL,
  updatedAt: new Date().toISOString(),
  posts,
};

await writeFile(OUTPUT_FILE, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
console.log(`Wrote ${posts.length} posts to ${OUTPUT_FILE}`);
