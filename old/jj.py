from playwright.sync_api import sync_playwright
import time
import os
import requests

base_url = 'https://www.dmo.gov.uk'
data_url = base_url + '/data/'
os.makedirs('dmo_data', exist_ok=True)

user_agent = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)

with sync_playwright() as p:
    # Launch browser (non-headless for better evasion; add stealth if needed)
    browser = p.chromium.launch(headless=False)  # Set True for faster runs once tested
    context = browser.new_context(
        user_agent=user_agent
    )
    page = context.new_page()
    page.goto(data_url)
    page.wait_for_load_state('networkidle')  # Wait for full load
    time.sleep(5)  # Extra buffer if JS is slow

    # Extract links
    report_links = []
    links = page.query_selector_all('a[href]')
    for link in links:
        href = link.get_attribute('href')
        if href and ('ExportReport?' in href or 'XmlDataReport?' in href or 'pdfdatareport?' in href):
            full_url = href if href.startswith('http') else base_url + href
            text = link.inner_text().strip()
            
            code = href.split('reportCode=')[-1].split('&')[0] if 'reportCode=' in href else 'unknown'
            ext = '.csv' if 'ExportReport' in href else '.xml' if 'XmlDataReport' in href else '.pdf'
            filename = f"{code}{ext}"
            report_links.append((full_url, filename, text))

    print(f"Found {len(report_links)} report links:")
    for _, fn, text in report_links[:20]:
        print(f"- {fn} → {text}")

    # Download using requests with cookies from Playwright for auth
    session = requests.Session()
    for cookie in context.cookies():
        session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])

    for url, filename, text in report_links:
        print(f"Downloading {filename} ({text})")
        try:
            r = session.get(url, headers={'User-Agent': user_agent})
            r.raise_for_status()
            with open(os.path.join('dmo_data', filename), 'wb') as f:
                f.write(r.content)
            time.sleep(2)
        except Exception as e:
            print(f"Error: {e}")

    browser.close()

print("Done!")
