# Privacy and Security

Portfolio Ops monitors a small list of **publicly accessible URLs**. It sends a normal unauthenticated `GET` request, follows ordinary redirects, and retains only endpoint status metadata: UTC date/time, target name, sanitized URL, final public redirect URL, HTTP status code, response time, success flag, normalized error category, bounded content-assertion result, DNS outcome, TLS expiry metadata, and header-presence posture.

It does not persist response bodies, cookies, complete request/response headers, identifiers, credentials, tokens, analytics data, IP addresses, certificates, or infrastructure details. Content assertions inspect at most 256 KB in memory and persist only a boolean result. It does not crawl links or inspect user-specific content.

No student, user, account, submission, document, or database information is accessed. No credentials are needed. WRepo remains a separate private application: this repository never accesses its source repository, database, internal APIs, authenticated pages, or private infrastructure.

Adding a target is appropriate only when the URL is intentionally public and safe to check without authentication. A Chrome Web Store listing is treated solely as a public availability endpoint; no reviews, identities, developer-console information, or account data is scraped.

This project observes public endpoints at scheduled intervals. It does not prove continuous uptime and does not access private application data.
