# Security and SSRF Protections

Targets must be public, credential-free HTTP(S) URLs. Configuration rejects malformed hostnames, `localhost`, `.local` names, loopback, private, link-local, reserved, and multicast IP literals. DNS checks reject targets whose answers contain no globally routable address before an HTTP request is attempted.

Redirect destinations are sanitized before recording. The monitor never stores response bodies, complete headers, cookies, authorization data, IP addresses, certificates, database URLs, student information, or private WRepo data. Content assertions are capped at 256 KB and only yield a boolean result.

GitHub issue automation is opt-in, uses `GITHUB_TOKEN` only in Actions, and sends only public incident metadata.
