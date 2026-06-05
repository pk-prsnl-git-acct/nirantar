import { writeFile } from "node:fs/promises";

const FEED_URL = "https://nirantar.substack.com/feed";
const RSS_JSON_URL = `https://api.rss2json.com/v1/api.json?rss_url=${encodeURIComponent(FEED_URL)}`;
const OUTPUT_FILE = "posts.json";
const MAX_POSTS = 6;

function decodeEntities(value = "") {
  return String(value)
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'");
}

function stripHtml(value = "") {
  return decodeEntities(value)
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function excerpt(value = "", maxLength = 190) {
  const text = stripHtml(value)
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

const response = await fetch(RSS_JSON_URL, {
  headers: {
    "accept": "application/json,text/plain,*/*",
    "user-agent": "Mozilla/5.0 (compatible; NirantarRSSBot/1.0; +https://nirantar.xyz)",
  },
});

if (!response.ok) {
  throw new Error(`Failed to fetch RSS JSON: ${response.status} ${response.statusText}`);
}

const data = await response.json();

if (data.status !== "ok" || !Array.isArray(data.items)) {
  throw new Error(`RSS JSON response was not usable: ${JSON.stringify(data).slice(0, 500)}`);
}

const posts = data.items
  .slice(0, MAX_POSTS)
  .map((item) => {
    const title = item.title || "The Still Signal";
    const link = item.link || "https://nirantar.substack.com";
    const publishedAt = item.pubDate || "";
    const issue = issueNumber(title, link);
    const date = dateLabel(publishedAt);

    return {
      title,
      link,
      pubDate: publishedAt ? new Date(publishedAt).toISOString() : "",
      dateLabel: issue ? `${issue} · ${date}` : date,
      description: excerpt(item.description || item.content || "Read the latest dispatch from The Still Signal."),
    };
  })
  .filter((post) => post.title && post.link);

if (!posts.length) {
  throw new Error("No posts found from RSS JSON.");
}

const payload = {
  source: FEED_URL,
  updatedAt: new Date().toISOString(),
  posts,
};

await writeFile(OUTPUT_FILE, `${JSON.stringify(payload, null, 2)}\n`, "utf8");

console.log(`Wrote ${posts.length} posts to ${OUTPUT_FILE}`);
