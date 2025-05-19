import atexit
from bs4 import BeautifulSoup
import os
import re
import requests
from requests.auth import HTTPBasicAuth
import tempfile


def fetch_html(url):
    """
    Fetch HTML content from a URL and save it to a temporary file.
    """
    temp_file = tempfile.NamedTemporaryFile(
        delete=False, suffix=".html", mode="w", encoding="utf-8"
    )
    temp_file_path = temp_file.name

    def cleanup_temp_file():
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

    atexit.register(cleanup_temp_file)

    response = requests.get(url)
    if response.status_code == 200:
        print("Data fetched successfully!")
        temp_file.write(response.text)
        temp_file.close()
        return temp_file_path
    else:
        print("Failed to fetch data:", response.status_code)
        print("Response:", response.text)
        temp_file.close()
        cleanup_temp_file()


def extract_news_articles(html_file):
    """
    Extract news articles, including timestamp, href and title, from the HTML file.
    """

    # Read the HTML file
    with open(html_file, "r", encoding="utf-8") as file:
        html_content = file.read()

    # Parse the HTML
    soup = BeautifulSoup(html_content, "html.parser")

    # Find the Nyheter heading - it's in an <h2> with a class "subheading"
    nyheter_heading = soup.find("h2", class_="subheading", string=re.compile("Nyheter"))

    if not nyheter_heading:
        print("No 'Nyheter' heading found")
        return []

    news_articles = []
    time_elements = nyheter_heading.find_parent().find_all("time")
    for time_element in time_elements:
        # Get the datetime attribute or the text content as fallback
        timestamp = time_element.get("datetime", time_element.text.strip())
        link_element = time_element.find_next("a")
        if link_element:
            href = link_element.get("href", "").strip()
            text = link_element.text.strip()
            timestamp = {"timestamp": timestamp, "href": href, "text": text}
        news_articles.append(timestamp)

    # Sort news_articles in descending order (latest date first)
    news_articles = sorted(news_articles, key=lambda x: x["timestamp"], reverse=True)
    return news_articles


def extract_press_release_data(html_file):
    """
    Extract press release data (title, intro, body) from the HTML file.
    """
    with open(html_file, "r", encoding="utf-8") as file:
        html_content = file.read()

    # Parse the HTML
    soup = BeautifulSoup(html_content, "html.parser")

    press_release_paragraph = soup.find(
        "p", string=re.compile(r"(Press release|Reports)", re.IGNORECASE)
    )

    if press_release_paragraph:
        # Find the first <h2> element within the same parent or context
        title_element = press_release_paragraph.find_next(
            "h2", string=re.compile("^Envirologic AB:", re.IGNORECASE)
        )
        title = (
            title_element.string.removeprefix("Envirologic AB:").strip()
            if title_element
            else None
        )
    else:
        title = None

    intro_div = press_release_paragraph.find_next("div", class_="intro")
    intro = intro_div.get_text(strip=True) if intro_div else None

    body_div = press_release_paragraph.find_next("div", class_="body")
    body = str(body_div) if body_div else None

    return title, intro, body


def publish_to_wordpress(title, intro, body):
    """
    Publish the extracted data to WordPress.
    """
    wp_url = "https://envirologic.se/wp-json/wp/v2/posts"

    username = "elin"
    app_password = "eigo E9w0 m766 mDa1 ivgp tXC7"

    data = {
        "title": title,
        "content": f"{intro}<br>{body}",
        "status": "publish",
        # "categories": [153], # This category ID is for experimenting with the plugin (publishes to wp-playground/*)
        "categories": [9],
        "type": "post",
        "comment_status": "open",
        "ping_status": "open",
    }

    response = requests.post(
        wp_url,
        json=data,
        auth=HTTPBasicAuth(username, app_password),
        headers={"Content-Type": "application/json"},
    )

    if response.status_code == 201:
        print(f"✅ Post published successfully to {response.json()['link']}")
    else:
        print("❌ Failed to publish post:", response.status_code)
        print("Response:", response.text)


if __name__ == "__main__":
    stockmarket_url = "https://www.spotlightstockmarket.com"
    instument_id_suffix = "/sv/bolag/irabout?InstrumentId=XSAT01001277"

    irabout_file = fetch_html(stockmarket_url + instument_id_suffix)
    news_articles = extract_news_articles(irabout_file)

    if news_articles:
        print(f"Found {len(news_articles)} news articles:")
        for i, article in enumerate(news_articles):
            print(
                f"  {i+1}) {article['timestamp']}: {article['text']}, {article['href']}"
            )

        user_input = (
            input("\nSelect the article that you want to upload (1):").strip().lower()
        )
        if user_input.isdigit() and 1 <= int(user_input) <= len(news_articles):
            article_file = fetch_html(
                stockmarket_url + news_articles[int(user_input) - 1]["href"],
            )
            title, intro, body = extract_press_release_data(article_file)
            publish_to_wordpress(title, intro, body)

        else:
            print("Invalid selection.")

    else:
        print("No timestamps found in the specified section.")
