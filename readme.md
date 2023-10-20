# News article project

## Project Overview

This project uses OpenAi's api to summarise news articles scrapped from BBC News Business. The types of articles summarised can be adjusted to suit the users preferences. The objective of the project was to produce 1 page daily news briefing that would allow me to quickly absorb relevant current news while also having the ability to access full articles if I so wished.

### Technologies used

- [OpenAI](https://openai.com/) to summarise using an NLP
- BeautifulSoup to scrape the web


## Installation

To install first clone this repository.
```bash
git clone https://github.com/HenryRees/news-summariser
cd news-summariser
```

### Requirements
* `python 3.10.6`

The code below shows how to setup a virtual environment and installs the dependencies.

    # Create a virtual environment (venv)
    make env

    # Activate the virtual environment
    source venv/bin/activate

    # Install project dependencies from requirements.txt
    make deps

## Project structure

The project has three main parts:

- Web scriping
- Natural Language Processing
- Email component

### Scrapping component

1. I use BeautifulSoup to scrape the BBC News Business articles that are available at "https://www.bbc.co.uk/news/business". During the scraping, I pull the article's url, title, content and publish date
2. After scraping I filter for articles which are less than --num_days old


### NLP component

1. The script utilises OpenAI's api to summarise the scraped news articles
2. The scraped articles are fedback into OpenAI's GPT-4 along with a user specified bio to filter for the most relevant articles
3. The OpenAI api is called again to further summarise the articles into a set a bullet points

### Email component

1. The script prepares a markdown script based on the summarise text provided by OpenAI's GPT-4
2. The markdwon script is then emailed to the user based on a user specified email
