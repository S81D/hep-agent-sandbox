#!/opt/conda/envs/hep/bin/python3 -I
"""Check an HTML page you built and report its problems as text instead of screenshots.

Usage:
    page-check PAGE.html [--any-host]
    page-check PAGE.html --shot shot.png [--selector CSS] [--width 390] [--dark]

Loads the page in headless Chromium (Playwright) at desktop (1280 px) and phone (390 px)
widths, each in light and dark mode, and reports:
  - JavaScript errors (console errors, uncaught exceptions) and missing local files
  - requests a published claude.ai artifact could not make: external scripts only from the
    CDN allowlist below, stylesheets only from Google Fonts, everything else inline.
    These are blocked here too, so the page looks as it will once published. For a page that
    is opened directly rather than published, --any-host lets external files load from anywhere.
  - horizontal overflow, naming the elements that stick out
  - TeX left as text (e.g. a literal "$\\sigma$") and KaTeX/MathJax error boxes
  - broken images and zero-size charts (canvas/svg)

Reading the report costs a few hundred tokens; a screenshot costs about width x height / 750
tokens and stays in the conversation. --shot saves one screenshot (the viewport, or one
element with --selector) for questions the report cannot answer, such as how a figure looks.

The page's folder is served to the browser under a private origin, so relative files (data,
scripts, images) load as they will once published; nothing outside that folder is served.

Exit status: 0 no problems, 1 problems found, 2 the page could not be checked.
"""
import argparse
import mimetypes
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

VIEWPORTS = [("desktop", 1280, 800), ("phone", 390, 844)]
THEMES = ["light", "dark"]
MAX_PAGE_BYTES = 16 * 1024 * 1024   # size limit of a published artifact page

# Origin the page folder is served from. Playwright answers these requests itself, so nothing
# listens on a port; *.localhost also counts as a secure context, like the https of claude.ai.
PAGE_ORIGIN = "https://page-check.localhost"

# What a published claude.ai artifact may load from outside the page (artifact rules, 2026-10),
# by request type, matched against the start of "host/path". Anything else external is blocked.
ALLOWED_SOURCES = {
    "script": ("cdnjs.cloudflare.com/", "cdn.jsdelivr.net/npm/", "unpkg.com/",
               "cdn.tailwindcss.com/", "code.jquery.com/"),
    "stylesheet": ("fonts.googleapis.com/",),
    "font": ("fonts.gstatic.com/",),
}

# Wait (at most 5 s) for web fonts and, if the page uses it, MathJax's asynchronous typesetting.
SETTLE = """() => Promise.race([
    Promise.all([document.fonts.ready, window.MathJax?.startup?.promise]).then(() => true),
    new Promise(resolve => setTimeout(resolve, 5000)),
])"""

# Runs inside the page and returns everything the report needs for one viewport and theme.
PAGE_PROBE = r"""() => {
  // Short CSS-like name for an element, e.g. table#yields.wide. One with neither id nor class
  // is named through its parents, e.g. "p.note > span".
  const describe = (el, depth = 0) => {
    let name = el.tagName.toLowerCase();
    if (el.id) name += '#' + el.id;
    const classes = typeof el.className === 'string' ? el.className.trim().split(/\s+/) : [];
    if (classes[0]) name += '.' + classes.slice(0, 2).join('.');
    const parent = el.parentElement;
    if (!el.id && !classes[0] && depth < 2 && parent && parent !== document.body) {
      name = describe(parent, depth + 1) + ' > ' + name;
    }
    return name;
  };
  // Elements under display:none (closed tabs, <details>) have no layout boxes
  const isShown = (el) => el.getClientRects().length > 0;

  // Horizontal overflow: the outermost elements whose right edge passes the viewport. Elements
  // inside a box that scrolls or clips horizontally are fine (e.g. a wide table in a scroller).
  const viewport = document.documentElement.clientWidth;
  const sticking = [];
  if (document.documentElement.scrollWidth > viewport + 1) {
    for (const el of document.body.querySelectorAll('*')) {
      const box = el.getBoundingClientRect();
      if (box.width === 0 || box.right <= viewport + 1) continue;
      let parent = el.parentElement, contained = false;
      while (parent && parent !== document.body) {
        if (sticking.includes(parent) || getComputedStyle(parent).overflowX !== 'visible') {
          contained = true;
          break;
        }
        parent = parent.parentElement;
      }
      if (!contained) sticking.push(el);
      if (sticking.length === 50) break;
    }
  }

  // TeX left as text: $$...$$, \(...\), \[...\], or $...$ containing a TeX command, _ or ^
  // (so prices like "$5" do not count). Rendered maths and code are skipped.
  const texPattern = /\$\$[\s\S]+?\$\$|\\\([\s\S]+?\\\)|\\\[[\s\S]+?\\\]|\$[^$\n]*[\\_^][^$\n]*\$/;
  const notProse = 'script, style, code, pre, textarea, math, .katex, .MathJax, mjx-container';
  const rawTex = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const parent = node.parentElement;
    if (!parent || parent.closest(notProse) || !isShown(parent)) continue;
    const match = node.textContent.match(texPattern);
    if (match) rawTex.push(describe(parent) + ': ' + match[0].slice(0, 50));
  }
  const mathErrors = [...document.querySelectorAll('.katex-error, mjx-merror')];

  const brokenImages = [...document.images]
    .filter(img => img.complete && img.naturalWidth === 0 && isShown(img))
    .map(img => img.getAttribute('src') || '(no src)');
  // Charts that failed to draw often leave a canvas or svg with no width or height
  const emptyGraphics = [...document.querySelectorAll('canvas, svg')]
    .filter(el => !el.parentElement.closest('svg') && isShown(el))
    .filter(el => { const box = el.getBoundingClientRect(); return box.width < 1 || box.height < 1; })
    .map(el => describe(el));

  const body = getComputedStyle(document.body);
  return {
    title: document.title,
    height: document.documentElement.scrollHeight,
    pageWidth: document.documentElement.scrollWidth,
    sticking: sticking.map(el => [describe(el), Math.round(el.getBoundingClientRect().width)]),
    rawTex: rawTex,
    mathErrors: mathErrors.length,
    firstMathError: mathErrors.length ? (mathErrors[0].title || mathErrors[0].textContent).slice(0, 100) : '',
    brokenImages: brokenImages,
    emptyGraphics: emptyGraphics,
    colours: [getComputedStyle(document.documentElement).backgroundColor, body.backgroundColor, body.color].join(' '),
    counts: {
      headings: document.querySelectorAll('h1, h2, h3').length,
      svg: [...document.querySelectorAll('svg')].filter(el => !el.parentElement.closest('svg')).length,
      canvas: document.querySelectorAll('canvas').length,
      images: document.images.length,
      tables: document.querySelectorAll('table').length,
    },
  };
}"""


@dataclass
class Target:
    """The page under test, and whether it may load external files from any host."""
    file: Path
    any_host: bool

    @property
    def folder(self):
        return self.file.parent

    @property
    def url(self):
        return f"{PAGE_ORIGIN}/{quote(self.file.name)}"


class RequestLog:
    """What the browser tried to load, and the script errors it saw, over all page loads."""

    def __init__(self):
        self.js_errors = []    # console errors and uncaught exceptions, first-seen order
        self.blocked = set()   # requests a published artifact may not make
        self.missing = set()   # local files that do not exist or lie outside the page folder
        self.failed = set()    # allowed requests that failed anyway (offline, wrong CDN path)

    def add_js_error(self, text):
        if text not in self.js_errors:
            self.js_errors.append(text)


def route_request(route, target, log):
    """Serve the page folder under PAGE_ORIGIN, let allowed external requests through, block the rest."""
    request = route.request
    url = urlsplit(request.url)
    if f"{url.scheme}://{url.netloc}" == PAGE_ORIGIN:
        relative = unquote(url.path).lstrip("/")
        local = (target.folder / relative).resolve()
        # resolve() collapses "../", so this also refuses paths that climb out of the folder
        if local.is_file() and local.is_relative_to(target.folder):
            content_type = mimetypes.guess_type(local.name)[0] or "application/octet-stream"
            # Artifact pages are often fragments without <meta charset>; they are UTF-8, and
            # without this Chromium would decode them as Windows-1252
            if content_type.startswith("text/") or content_type in ("application/javascript", "application/json"):
                content_type += "; charset=utf-8"
            route.fulfill(path=local, content_type=content_type)
        else:
            if relative != "favicon.ico":   # requested by the browser itself, not the page
                log.missing.add(relative)
            route.fulfill(status=404, body="")
    elif target.any_host or (url.netloc + url.path).startswith(ALLOWED_SOURCES.get(request.resource_type, ())):
        route.continue_()
    else:
        log.blocked.add(f"{request.resource_type} {request.url[:120]}")
        route.abort("blockedbyclient")


def open_page(browser, target, log, width, height, dark):
    """Load the page in a fresh browser context and let it settle; returns (context, page)."""
    context = browser.new_context(viewport={"width": width, "height": height},
                                  color_scheme="dark" if dark else "light")
    context.route("**/*", lambda route: route_request(route, target, log))
    page = context.new_page()

    def on_console(message):
        # "Failed to load resource" repeats what the request log already reports
        if message.type != "error" or message.text.startswith("Failed to load resource"):
            return
        where = message.location
        source = f" ({Path(urlsplit(where['url']).path).name}:{where['lineNumber'] + 1})" if where.get("url") else ""
        log.add_js_error(message.text[:200] + source)

    def on_request_failed(request):
        if "BLOCKED_BY_CLIENT" not in (request.failure or ""):   # blocked by route_request
            log.failed.add(f"{request.url[:120]} ({request.failure})")

    page.on("console", on_console)
    page.on("pageerror", lambda error: log.add_js_error(f"uncaught {error.name}: {error.message}"[:200]))
    page.on("requestfailed", on_request_failed)

    page.goto(target.url, wait_until="load", timeout=30_000)
    try:
        # CDN scripts and charts often finish after the load event
        page.wait_for_load_state("networkidle", timeout=5_000)
    except PlaywrightTimeout:
        pass
    page.evaluate(SETTLE)
    return context, page


def layout_findings(result, viewport_width):
    """Problems that depend on viewport and theme, as report lines (empty list if none)."""
    found = []
    if result["pageWidth"] > viewport_width + 1:
        # Identical offenders (e.g. many unstyled maths spans) are counted, not repeated
        offenders = Counter(f"{name} ({width} px)" for name, width in result["sticking"])
        sticking = ", ".join(name if n == 1 else f"{name} x{n}" for name, n in list(offenders.items())[:3])
        found.append(f"page is {result['pageWidth']} px wide in a {viewport_width} px viewport; "
                     f"sticks out: {sticking}")
    if result["rawTex"]:
        found.append(f"unrendered TeX ({len(result['rawTex'])}): " + "; ".join(result["rawTex"][:3]))
    if result["mathErrors"]:
        found.append(f"{result['mathErrors']} KaTeX/MathJax error box(es), first: {result['firstMathError']}")
    if result["brokenImages"]:
        found.append("broken images: " + ", ".join(result["brokenImages"][:3]))
    if result["emptyGraphics"]:
        found.append("zero-size charts/graphics: " + ", ".join(result["emptyGraphics"][:3]))
    return found


def take_shot(browser, target, log, args):
    """Save one screenshot (viewport, or the --selector element); returns the report line."""
    height = {width: height for _, width, height in VIEWPORTS}.get(args.width, 800)
    context, page = open_page(browser, target, log, args.width, height, args.dark)
    options = {"path": args.shot}
    if args.shot.lower().endswith((".jpg", ".jpeg")):
        options["quality"] = 70
    if args.selector:
        element = page.locator(args.selector).first
        if element.count() == 0:
            context.close()
            return f"  FAIL  --shot: no element matches {args.selector!r}"
        element.screenshot(**options)
        box = element.bounding_box()
        width, height = round(box["width"]), round(box["height"])
    else:
        page.screenshot(**options)   # the viewport only, never the full page
        width = args.width
    context.close()
    return f"  shot  {args.shot} ({width} x {height} px, about {width * height // 750} tokens to view)"


def report(target, results, log, shot_line):
    """Print the report; returns the exit status (0 no problems, 1 problems)."""
    desktop = results[("desktop", "light")]
    counts = desktop["counts"]
    size = target.file.stat().st_size
    hosts = "; any host allowed" if target.any_host else ""
    print(f'page-check: {target.file.name} ({size / 1024:.1f} kB{hosts}) "{desktop["title"]}"')
    print(f"  {counts['headings']} headings, {counts['svg']} svg, {counts['canvas']} canvas, "
          f"{counts['images']} images, {counts['tables']} tables; {desktop['height']} px tall on desktop")

    # Group identical findings so e.g. one overflow seen in both phone themes prints once
    clean, variants_by_finding = [], {}
    for name, width, _ in VIEWPORTS:
        for theme in THEMES:
            findings = layout_findings(results[(name, theme)], width)
            if not findings:
                clean.append(f"{name} {theme}")
            for finding in findings:
                variants_by_finding.setdefault(finding, []).append(f"{name} {theme}")

    problems = [f"{', '.join(variants)}: {finding}" for finding, variants in variants_by_finding.items()]
    problems += [f"JavaScript: {error}" for error in log.js_errors]
    problems += [f"blocked once published: {request}" for request in sorted(log.blocked)]
    problems += [f"missing local file: {path}" for path in sorted(log.missing)]
    problems += [f"request failed: {request}" for request in sorted(log.failed)]
    if size > MAX_PAGE_BYTES:
        problems.append(f"page is {size / 2**20:.1f} MB; published pages are limited to 16 MB")

    if clean:
        print(f"  OK    {', '.join(clean)}")
    for problem in problems:
        print(f"  FAIL  {problem}")
    # Only a note: a page without dark-mode styles is legitimate, just worth knowing
    if results[("desktop", "light")]["colours"] == results[("desktop", "dark")]["colours"]:
        print("  NOTE  same colours in light and dark mode (no prefers-color-scheme styles)")
    if shot_line:
        print(shot_line)
    print(f"{len(problems)} problem(s)" if problems else "no problems found")
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("page", help="the HTML file to check")
    parser.add_argument("--any-host", action="store_true",
                        help="the page is opened directly, not published as an artifact: load external files from any host")
    parser.add_argument("--shot", metavar="FILE", help="also save one screenshot (.png, or .jpg for smaller files)")
    parser.add_argument("--selector", metavar="CSS", help="screenshot only this element, e.g. '#fig2'")
    parser.add_argument("--width", type=int, default=1280, help="screenshot viewport width (default 1280; phone 390)")
    parser.add_argument("--dark", action="store_true", help="screenshot in dark mode")
    args = parser.parse_args()
    if not args.shot and (args.selector or args.dark or args.width != 1280):
        parser.error("--selector, --width and --dark only apply with --shot")

    page_file = Path(args.page).resolve()
    if not page_file.is_file():
        print(f"page-check: no such file: {args.page}", file=sys.stderr)
        return 2
    target = Target(page_file, args.any_host)

    log = RequestLog()
    results = {}
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
            for name, width, height in VIEWPORTS:
                for theme in THEMES:
                    context, page = open_page(browser, target, log, width, height, theme == "dark")
                    results[(name, theme)] = page.evaluate(PAGE_PROBE)
                    context.close()
            shot_line = take_shot(browser, target, log, args) if args.shot else None
            browser.close()
        except PlaywrightError as error:
            print(f"page-check: could not check {page_file}: {error.message.splitlines()[0]}", file=sys.stderr)
            return 2
    return report(target, results, log, shot_line)


if __name__ == "__main__":
    sys.exit(main())
