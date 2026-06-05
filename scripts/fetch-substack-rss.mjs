import { writeFile } from "node:fs/promises";

const ARCHIVE_URL = "https://nirantar.substack.com/api/v1/archive?sort=new&search=&offset=0&limit=6";
const OUTPUT_FILE = "posts.json";
const MAX_POSTS = 6;

function stripHtml(value = "") {
  return String(value)
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

function issueNumber(title = "", slug = "") {
  const haystack = `${title} ${slug}`;
  const match = haystack.match(/issue[-_\s#]*(\d+)/i);
  return match ? `Issue #${match[1].padStart(3, "0")}` : "";
}

async function fetchJson(url) {
  const response = await fetch(url, {
    headers: {
      "accept": "application/json,text/plain,*/*",
      "user-agent": "Mozilla/5.0 (compatible; NirantarRSSBot/1.0; +https://nirantar.xyz)",
      "referer": "https://nirantar.substack.com/",
      "origin": "https://nirantar.substack.com",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch Substack archive: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

const archive = await fetchJson(ARCHIVE_URL);

const items = Array.isArray(archive)
  ? archive
  : Array.isArray(archive.posts)
    ? archive.posts
    : [];

const posts = items
  .slice(0, MAX_POSTS)
  .map((item) => {
    const title = item.title || item.subtitle || "The Still Signal";
    const slug = item.slug || "";
    const link = item.canonical_url || item.web_url || `https://nirantar.substack.com/p/${slug}`;
    const publishedAt =
      item.post_date ||
      item.published_at ||
      item.publish_date ||
      item.created_at ||
      "";

    const description =
      item.subtitle ||
      item.description ||
      item.search_engine_description ||
      item.truncated_body_text ||
      item.preview ||
      "";

    const issue = issueNumber(title, slug);
    const date = dateLabel(publishedAt);

    return {
      title,
      link,
      pubDate: publishedAt ? new Date(publishedAt).toISOString() : "",
      dateLabel: issue ? `${issue} · ${date}` : date,
      description: excerpt(description || "Read the latest dispatch from The Still Signal."),
    };
  })
  .filter((post) => post.title && post.link);

if (!posts.length) {
  throw new Error("No posts found from Substack archive endpoint.");
}

const payload = {
  source: ARCHIVE_URL,
  updatedAt: new Date().toISOString(),
  posts,
};

await writeFile(OUTPUT_FILE, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
console.log(`Wrote ${posts.length} posts to ${OUTPUT_FILE}`);
