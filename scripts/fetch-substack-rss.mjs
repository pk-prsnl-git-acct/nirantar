import { readFile, writeFile } from "node:fs/promises";

const FEED_URL = "https://nirantar.substack.com/feed";
const ARCHIVE_URL = "https://nirantar.substack.com/api/v1/archive?sort=new&search=&offset=0&limit=6";
const OUTPUT_FILE = "posts.json";
const MAX_POSTS = 6;
const FEED_FILE = process.env.RSS_FEED_FILE || "";

function decodeEntities(value = "") {
  return String(value)
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
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
  const match = haystack.match(/issue[-_\s#|]*(\d+)/i);
  return match ? `Issue #${match[1].padStart(3, "0")}` : "";
}

function extractTag(block, tagName) {
  const match = block.match(new RegExp(`<${tagName}\\b[^>]*>([\\s\\S]*?)<\\/${tagName}>`, "i"));
  return match ? decodeEntities(match[1]).trim() : "";
}

function parseFeedItems(xml) {
  const itemBlocks = xml.match(/<item\b[\s\S]*?<\/item>/gi) || [];

  return itemBlocks.map((block) => ({
    title: extractTag(block, "title"),
    link: extractTag(block, "link"),
    pubDate: extractTag(block, "pubDate"),
    description: extractTag(block, "description"),
    content: extractTag(block, "content:encoded"),
  }));
}

function parseArchiveItems(jsonText) {
  const data = JSON.parse(jsonText);
  const items = Array.isArray(data) ? data : Array.isArray(data.posts) ? data.posts : [];

  return items.map((item) => ({
    title: item.title || item.subtitle || "",
    link: item.canonical_url || item.web_url || (item.slug ? `https://nirantar.substack.com/p/${item.slug}` : ""),
    pubDate: item.post_date || item.published_at || item.publish_date || item.created_at || "",
    description:
      item.subtitle ||
      item.description ||
      item.search_engine_description ||
      item.truncated_body_text ||
      item.preview ||
      "",
    content: item.body_html || item.description || "",
  }));
}

const sourceText = FEED_FILE
  ? await readFile(FEED_FILE, "utf8")
  : await (async () => {
      const response = await fetch(ARCHIVE_URL, {
        headers: {
          accept: "application/json,text/plain,*/*",
          "accept-language": "en-US,en;q=0.9",
          origin: "https://nirantar.substack.com",
          referer: "https://nirantar.substack.com/",
          "user-agent": "Mozilla/5.0 (compatible; NirantarRSSBot/1.0; +https://nirantar.xyz)",
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch Substack archive: ${response.status} ${response.statusText}`);
      }

      return response.text();
    })();

const trimmedSource = sourceText.trim();
const items = trimmedSource.startsWith("[") || trimmedSource.startsWith("{")
  ? parseArchiveItems(sourceText)
  : parseFeedItems(sourceText);

const posts = items
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
  throw new Error("No posts found in Substack source.");
}

const payload = {
  source: trimmedSource.startsWith("[") || trimmedSource.startsWith("{") ? ARCHIVE_URL : FEED_URL,
  updatedAt: new Date().toISOString(),
  posts,
};

await writeFile(OUTPUT_FILE, `${JSON.stringify(payload, null, 2)}\n`, "utf8");

console.log(`Wrote ${posts.length} posts to ${OUTPUT_FILE}`);
