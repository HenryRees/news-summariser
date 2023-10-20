import openai
import json
import requests
import pytz
import re
import os
import argparse
import smtplib
import markdown
from dotenv import load_dotenv
from datetime import date, timedelta, datetime
from dateutil.parser import parse
from tqdm import tqdm
from bs4 import BeautifulSoup
from glob import glob
from datetime import date
from templates import MARKDOWN_HEADING
from templates import MARKDOWN_CONTENT
from templates import MARKDOWN_END
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# Global variables

timezone = pytz.UTC
load_dotenv()
openai.api_key = os.environ["OPENAI_API_KEY"]
sender_email = os.environ["SENDER_EMAIL"]
sender_password = os.environ["SENDER_PASSWORD"]


class NewsArticle:
    def __init__(self, title: str, url: str, content: str):
        self.title = title
        self.url = url
        self.content = content


class NewsArticleWithSummary:
    def __init__(self, news_article: NewsArticle, summary: str):
        self.news_article = news_article
        self.summary = summary

    @property
    def title(self):
        return self.news_article.title

    @property
    def url(self):
        return self.news_article.url


def scrape_links(URL: str = "https://www.bbc.co.uk/news/business"):
    URL = URL
    site = requests.get(URL)

    main_soup = BeautifulSoup(site.content, "html.parser")
    link_selections = main_soup.select("a")
    web_links = [str(link_selection["href"]) for link_selection in link_selections]
    article_links = []
    for web_link in web_links:
        if (
            len(web_link) == 23 and web_link[:15] == "/news/business-"
        ):  # Is there a better way to filter links
            article_links.append("https://www.bbc.co.uk" + web_link)
    article_links = list(set(article_links))  # deduplicate list
    return article_links


def scrape_content(
    num_days: int,
    article_URL: str = "https://www.bbc.co.uk/news/business-67015663",
) -> NewsArticle | None:
    URL = article_URL
    secondary_site = requests.get(URL)

    link_soup = BeautifulSoup(secondary_site.content, "html.parser")
    article_time = link_soup.find("time")
    if article_time is None:
        return None
    article_datetime: datetime = parse(str(article_time.get("datetime")))  # type: ignore
    time_difference = datetime.now(timezone) - article_datetime

    if time_difference > timedelta(days=num_days):
        return None

    article_heading = link_soup.find(id="main-heading")
    if article_heading is None:
        print(f"Could not find article at {article_URL}, skipping...")
        return None
    link_contents = link_soup.select("main")[0].find_all("p")
    content = []
    for link_content in link_contents:
        if "class" not in link_content.attrs or "PromoHeadline" not in link_content.attrs["class"][0]:
            content.append(link_content.text)
    article_content = " ".join(content)
    return NewsArticle(article_heading.text, article_URL, article_content)


def load_data() -> list:
    # Opening JSON file
    paths = glob("News_articles/blogs_*.json")[:5]
    news_articles = []
    for path in paths:
        with open(path) as fh:
            data = json.load(fh)
            news_articles.append(NewsArticle(data["title"], "url", data["text"]))
    return news_articles


def call_openai(text: str, model="gpt-4") -> str:
    response = openai.ChatCompletion.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": text},
        ],
    )

    output_message = response.choices[0]["message"]["content"]  # type: ignore
    return output_message


def article_filter(
    article_titles: list[str], num_articles: int, bio: str
) -> list[int] | None:
    title_list = "/n".join([f"{i}: {title}" for i, title in enumerate(article_titles)])

    message_text = f""" {bio}

Choose {num_articles} which you think will be of interest to me"

{title_list}

Please respond with the numbers of the articles you would choose in the format [x, y, ..., z] where x, y, z represent the article numbers and there are {num_articles} numbers.
"""

    article_filter_response = call_openai(message_text)

    # Define a regex pattern to match square brackets
    pattern = r"\[(.*?)\]"
    match = re.search(pattern, article_filter_response)

    articles_to_filter = []
    
    if match:
        filter_contents = match.group(1)
        articles_to_filter = [int(num) for num in filter_contents.split(",")]
    if len(articles_to_filter) > num_articles:
        articles_to_filter = articles_to_filter[:num_articles]
    else:
        return None
    

    return articles_to_filter


def articles_summarise(
    news_articles: list[NewsArticle],
) -> list[NewsArticleWithSummary]:
    news_articles_summarised = []
    for news_article in tqdm(news_articles, desc="Summarising articles"):
        message_text = f"Please summarise the following news article in 4 sentences. /n {news_article.content} "
        news_article_summarised = NewsArticleWithSummary(
            news_article, call_openai(message_text)
        )
        news_articles_summarised.append(news_article_summarised)
    return news_articles_summarised


def generate_intro(
    news_articles_summarised: list[NewsArticleWithSummary],
) -> str | None:
    summaries = [s.summary for s in news_articles_summarised]
    summary_list = "/n".join([f"{i}: {summary}" for i, summary in enumerate(summaries)])

    message_text = f"""Produce {len(news_articles_summarised)} bullet points, which are 1 sentence long, based on these news article summaries:

{summary_list}

Please respond with just the bullet points
"""

    article_intro = call_openai(message_text)

    return article_intro


def generate_markdown(
    news_articles_summarised: list[NewsArticleWithSummary], article_intro
) -> str:
    markdown_script = MARKDOWN_HEADING.replace("<ARTICLE_INTRO>", article_intro)

    for news_article_summarised in news_articles_summarised:
        markdown_content = (
            MARKDOWN_CONTENT.replace("<ARTICLE_TITLE>", news_article_summarised.title)
            .replace("<ARTICLE_URL>", news_article_summarised.url)
            .replace("<ARTICLE_CONTENT>", news_article_summarised.summary)
        )

        markdown_script += markdown_content

    markdown_script += MARKDOWN_END

    return markdown_script

def send_email(recipient_email, message_script):
    
    subject = "Daily Newsletter"

    smtp_server = "smtp.gmail.com"  # Use the SMTP server of your email provider
    smtp_port = 587  # Port for Gmail is 587
    smtp_username = sender_email
    smtp_password = sender_password

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = recipient_email
    message["Subject"] = subject
    html_text = markdown.markdown(message_script)
    message.attach(MIMEText(html_text, "html"))

    server = smtplib.SMTP(smtp_server, smtp_port)
    server.starttls()
    server.login(smtp_username, smtp_password)

    server.sendmail(sender_email, recipient_email, message.as_string())

    server.quit()

def main(email_address: str, num_articles: int, num_days: int, bio: str):
    news_articles = []
    article_titles = []
    
    for article_link in tqdm(scrape_links(), desc="Scraping Links"):
        news_article = scrape_content(num_days, article_link)
        if news_article is None:
            continue
        news_articles.append(news_article)
        article_titles.append(news_article.title)

    if len(news_articles) <= num_articles:
        articles_to_filter = None
    else:
        articles_to_filter = article_filter(article_titles, num_articles, bio)
    if articles_to_filter is None:
        filtered_list = news_articles
    else:
        filtered_list = [
            e for i, e in enumerate(news_articles) if i in articles_to_filter
        ]

    news_articles_summarised = articles_summarise(filtered_list)

    article_intro = generate_intro(news_articles_summarised)
    markdown_script = generate_markdown(news_articles_summarised, article_intro)

    output_directory = "outputs"
    file_name = "Daily Business News " + str(date.today())
    output_path = os.path.join(output_directory, file_name)

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    with open(output_path, "w", encoding="utf-8") as file:
        file.write(markdown_script)
    
    send_email(email_address, markdown_script)
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="News summariser")

    parser.add_argument(
        "email_address", type=str, help="Please enter your email"
    )
    
    parser.add_argument(
        "--num_articles", type=int, default=5, help="Number of articles to summarise"
    )
    parser.add_argument(
        "--num_days", type=int, default=1, help="How old do you want the articles to be"
    )
    parser.add_argument(
        "--bio",
        type=str,
        default="I am a managment consultant with a keen interest in the US and UK financial markets and the transport sector.",
        help="What are you interested in, this will help the AI filter the news articles for you",
    )

    args = parser.parse_args()

    main(args.email_address, args.num_articles, args.num_days, args.bio)
