# Admin hardening (parked)

> Status: **not started**. Written 2026-10-19 so we can pick it up later.

Ideas for protecting the staff admin at `/new/admin/` from scraping, bots and password guessing. They're listed in the order we'd do them. Item 1 is the real protection; the rest add to it.

The site sits behind Cloudflare, then a Linode NodeBalancer (where TLS ends), then nginx on the host (`nginx/conf.d/basketful.conf`). The admin is a static React app served from a container on `127.0.0.1:8081`. Everything it does goes through the Django API at `/api/v1/`, which the participant app at `/cart/` uses too.

## 1. Fix login rate limiting behind the proxies (do this first)

**The problem.** DRF's login throttle (`LoginRateThrottle`, 5/minute, in `apps/account/api/auth_views.py`) identifies clients with `get_ident()`. `REST_FRAMEWORK` doesn't set `NUM_PROXIES`, so DRF uses the whole `X-Forwarded-For` header as the client's identity. Cloudflare and nginx (`$proxy_add_x_forwarded_for`) add to whatever header the client sent rather than replacing it. So anyone can send a different `X-Forwarded-For: <random>` with each request and get a new 5-per-minute allowance every time, which makes password guessing effectively unthrottled. The same applies to every anonymous throttle (`anon`, `login`).

**The fix.**
- In the host nginx `location /` block, pass the address Cloudflare saw, which the client can't change:
  ```nginx
  proxy_set_header X-Real-IP $http_cf_connecting_ip;
  ```
- Make Django trust only that header. Either subclass the throttles to read `HTTP_X_REAL_IP`, or set `NUM_PROXIES` to the exact number of proxies in the chain (Cloudflare, NodeBalancer, nginx) so DRF takes the right entry from `X-Forwarded-For`.
- Don't trust `CF-Connecting-IP` unless requests can only arrive through Cloudflare. Check that the NodeBalancer or firewall only accepts Cloudflare's IP ranges; otherwise someone could skip Cloudflare and set the header themselves.
- Add a test: two login requests with different made-up `X-Forwarded-For` values must share one rate-limit bucket.

## 2. Cloudflare Access in front of `/new/admin/`

Cloudflare asks for a login before the request reaches the server, so scrapers and bots only see Cloudflare's login page. It's free for up to 50 users, and there's no code to change.

1. In Cloudflare, go to **Zero Trust → Access → Applications → Add → Self-hosted**.
2. Set the domain to `basketful.lovewm.org` and the path to `new/admin`.
3. Add a policy that allows emails ending in `@lovewm.org`, or a list of staff emails. Staff get a one-time code by email, then sign in to Basketful as usual.

Don't put Access on `/api/`. The participant app at `/cart/` calls the same API, so participants would be blocked.

## 3. Keep the admin out of search engines

Add this to the host nginx `location ^~ /new/admin/` block:
```nginx
    add_header X-Robots-Tag "noindex, nofollow" always;
```
Don't list the path in `robots.txt`. That file is public, so it would advertise where the admin is.

## 4. Challenge bots with a Cloudflare rule

This is a lighter option than Access. Under **Security → WAF → Custom rules**, add a rule: if the URI path starts with `/new/admin` and the visitor isn't a known good bot, show a **Managed Challenge**.

## 5. Obscurity: rename the admin path

Moving `/new/admin/` to something unguessable (say `/staff-<random>/`) stops scanners that probe common paths. It does nothing against anyone who learns the URL, and the API stays at `/api/v1/`, so it only adds to items 1–4 and doesn't replace them.

The path is set when the image is built, so renaming it takes the same changes as the `/cart/` move:
- `.github/workflows/frontend-ci.yml`: `VITE_BASE_PATH` for the admin, in both the build check and the Docker build args
- `frontend/vite.config.ts`: the fallback path
- `frontend/nginx.conf`: the `location` blocks and the `try_files` fallback
- `nginx/conf.d/basketful.conf` and the live config on the server
- the docs that mention `/new/admin/` (`DEPLOYMENT.md`, `CI.md`, `docs/diagrams/infrastructure.mmd`)
- the react-admin router `basename`, if it isn't already derived from `import.meta.env.BASE_URL`

Deploy it in the same order as the `/cart/` move: build and run the new image first, then switch nginx.
