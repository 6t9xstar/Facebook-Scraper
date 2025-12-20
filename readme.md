# Facebook Email Extraction Tool

## Background

You currently extract emails from Facebook pages manually by:
- Opening ~50 Facebook page URLs at once using a multi-link opener browser extension
- Running an email-hunter browser extension that scans visible page content
- Saving discovered emails manually

This workflow works but is:
- Slow due to browser overhead and manual steps
- Resource-heavy (many tabs, UI rendering)
- Dependent on multiple extensions

You want a **free, lightweight, fast, and smooth software solution** for **personal use only** that automates this process.

**Assumptions (please confirm):**
- You only want to extract **publicly visible emails** (About section, page description, posts)
- You do **not** want to bypass Facebook authentication, paywalls, or privacy controls
- You are okay running a local script/app on your PC (not a cloud SaaS)

---

## Requirements

### Must Have
- Accept a list of 80+ Facebook Page URLs as input
- Automatically load each page and scan for email addresses
- Extract and save emails to a local file (CSV / TXT)
- Be free and open-source based
- Faster than opening pages manually in a browser

### Should Have
- Headless operation (no visible browser UI)
- Rate limiting to avoid Facebook temporary blocks
- Resume capability if interrupted

### Could Have
- Deduplication of emails
- Basic logging (URL → email found / not found)

### Won’t Have
- Hacking private data
- Scraping personal profiles (non-pages)
- Commercial-scale scraping

---

## Method

### High-Level Architecture

The software will be a **local Windows-based Python application** that uses a **headless browser** to load Facebook Pages and extract **publicly visible email addresses**.

It mimics what you do manually, but without UI rendering or extensions.

```
Input URLs (.txt)
        ↓
Headless Browser (Playwright)
        ↓
Page Content (About + Visible Text)
        ↓
Email Extraction (Regex)
        ↓
Results (CSV / TXT)
```

---

### Technology Stack (All Free)

- **Language:** Python 3.11+
- **Browser Automation:** Playwright (Chromium)
- **Parsing:** Built-in text extraction (no DOM hacking)
- **Email Detection:** Regex (RFC-compliant)
- **Output:** CSV file
- **Packaging (optional):** PyInstaller → `.exe`

---

### Why Headless Browser (Important)

Facebook Pages:
- Load content dynamically (JavaScript)
- Hide emails in About sections

Playwright:
- Executes JavaScript like a real browser
- Faster than Selenium
- Less detectable
- No visible tabs

---

### Email Extraction Algorithm

1. Load Facebook Page URL
2. Wait for page network to become idle
3. Extract **all visible text**
4. Run regex pattern:

```
[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}
```

5. Normalize emails (lowercase)
6. Deduplicate
7. Store result mapped to URL

---

### Rate Limiting Strategy

To avoid Facebook blocking:
- Max 3–5 pages in parallel
- 2–4 seconds delay between batches
- Randomized wait (human-like)

---

## Implementation

### Step 1: Install Python

- Download from python.org
- Enable **Add Python to PATH**

Verify:
```
python --version
```

---

### Step 2: Install Dependencies

```
pip install playwright pandas
playwright install chromium
```

---

### Step 3: Project Structure

```
facebook_email_extractor/
├── input_urls.txt
├── extractor.py
├── results.csv
└── logs.txt
```

---

### Step 4: Core Script Logic (extractor.py)

- Read URLs from `input_urls.txt`
- Launch Playwright in headless mode
- Process URLs in async batches
- Extract text using `page.inner_text('body')`
- Apply regex
- Save results

---

### Step 5: Output Format

**results.csv**

| Facebook URL | Email Found |
|-------------|------------|
| fb.com/QCA… | qcaelectric@mchsi.com |

---

### Step 6: Optional – Build EXE

```
pip install pyinstaller
pyinstaller --onefile extractor.py
```

Result:
```
dist/extractor.exe
```

Double-click to run.

---

## Milestones

1. Environment setup complete
2. URLs loading correctly
3. Email extraction verified on 10 pages
4. CSV output validated
5. EXE build completed

---

## Gathering Results

- Success rate: % pages with emails found
- Speed: URLs/minute
- Accuracy: Emails match Facebook About section
- Stability: No crashes on 80+ URLs

---

## Need Professional Help in Developing Your Architecture?

Please contact me at https://sammuti.com 🙂
(TBD)

## Milestones
(TBD)

## Gathering Results
(TBD)

## Need Professional Help in Developing Your Architecture?

Please contact me at https://sammuti.com 🙂

