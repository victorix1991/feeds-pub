// Fetch a few public RSS feeds and hand each one, unchanged, to a signed ingest endpoint.
// Endpoint URL and key come from repository secrets. Logs print counts only; no feed content is committed.
import crypto from "node:crypto";
const FEEDS = {
  "ext-sspai": "http://sspai.me/feed",
  "ext-ifanr": "http://www.ifanr.com/feed",
  "ext-apprcn": "http://free.apprcn.com/feed/",
  "ext-appinn": "http://feed.appinn.com/",
  "ext-ruyo": "https://51.ruyo.net/feed",
};
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";
const URL_ = process.env.PUSH_URL, KEY = process.env.PUSH_KEY;
if (!URL_ || !KEY) { console.log("missing config"); process.exit(1); }
const key = Buffer.from(KEY, "base64");
async function get(u) {
  for (let a = 1; a <= 2; a++) {
    try {
      const r = await fetch(u, { headers: { "user-agent": UA, accept: "application/rss+xml, application/atom+xml, application/xml, text/xml, */*" }, signal: AbortSignal.timeout(25000) });
      if (r.ok) return await r.text();
      if (r.status < 500) throw new Error("HTTP " + r.status);
    } catch (e) { if (a === 2) throw e; }
    await new Promise((s) => setTimeout(s, 3000));
  }
}
async function push(feed, xml) {
  const body = Buffer.from(JSON.stringify({ feed, xml, raw: true }));
  const ts = Math.floor(Date.now() / 1000);
  const bh = crypto.createHash("sha256").update(body).digest("hex");
  const path = new URL(URL_).pathname;
  const sig = crypto.createHmac("sha256", key).update(ts + "|" + path + "|" + bh).digest("hex");
  const r = await fetch(URL_, { method: "POST", body, headers: { "content-type": "application/json", "user-agent": UA, "x-push-ts": String(ts), "x-push-sig": sig }, signal: AbortSignal.timeout(30000) });
  return r.status;
}
let ok = 0, n = 0;
for (const [feed, u] of Object.entries(FEEDS)) {
  n++;
  try {
    const xml = await get(u);
    const items = (xml.match(/<item[\s>]|<entry[\s>]/g) || []).length;
    if (!/<(rss|feed|rdf:RDF)[\s>]/.test(xml) || !items) { console.log(feed, "bad feed"); continue; }
    const st = await push(feed, xml);
    console.log(feed, items, "items, push", st === 200 ? "ok" : "fail " + st);
    if (st === 200) ok++;
  } catch (e) { console.log(feed, "fetch fail", String(e.message || e).replace(/https?:\/\/\S+/g, "").slice(0, 60)); }
}
console.log(`${ok}/${n} feeds ok`);
process.exit(ok === n ? 0 : ok ? 0 : 1);
