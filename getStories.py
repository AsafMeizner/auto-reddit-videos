from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import json

# Subreddits to scrape
subreddits = ['stories', 'RedditStoryTime', 'AmItheAsshole']

# Base URL format for subreddit (set to Top posts of all time)
base_url = "https://www.reddit.com/r/{}/top/?t=all"

# List to hold all the posts
posts_data = []

# Function to scrape subreddit using Selenium and scroll to load more posts
def scrape_subreddit(subreddit, max_posts=50):
    url = base_url.format(subreddit)
    driver.get(url)
    time.sleep(5)  # Wait for the page to load (adjust this if needed)

    post_count = 0
    last_height = driver.execute_script("return document.body.scrollHeight")

    while post_count < max_posts:
        # Locate all articles (posts) in the subreddit
        posts = driver.find_elements(By.CSS_SELECTOR, 'article.w-full')  # CSS selector for the article container
        
        for post in posts:
            if post_count >= max_posts:
                break

            try:
                # Find the title within the post
                title_element = post.find_element(By.CSS_SELECTOR, 'a[slot="title"]')
                post_title = title_element.text

                # Scroll to the element to ensure it's in view
                driver.execute_script("arguments[0].scrollIntoView(true);", title_element)
                time.sleep(1)  # Allow time for the scroll to complete

                # Use JavaScript to click on the element to avoid the click interception issue
                driver.execute_script("arguments[0].click();", title_element)
                time.sleep(3)  # Give time for the page to load fully

                # Extract the full post content from the opened page
                full_text_element = driver.find_element(By.CSS_SELECTOR, 'div[data-post-click-location="text-body"]')
                full_text = full_text_element.text

                # Save post data
                post_data = {
                    'subreddit': subreddit,
                    'title': post_title,
                    'text': full_text
                }
                posts_data.append(post_data)
                post_count += 1

                # Navigate back to the subreddit page to scrape the next post
                driver.back()
                time.sleep(2)  # Wait for the page to reload after going back

            except Exception as e:
                print(f"Error processing post: {e}")

        # Scroll down to load more posts
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)  # Wait for new posts to load

        # Check if we've reached the bottom of the page (no more new posts)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            print(f"No more posts to load for {subreddit}.")
            break
        last_height = new_height

# Setup Selenium WebDriver (Using Chrome in this case)
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

# Scrape all subreddits
for subreddit in subreddits:
    print(f"Scraping {subreddit}...")
    scrape_subreddit(subreddit, max_posts=50)  # Set the number of max posts to scrape per subreddit

# Close the browser
driver.quit()

# Save the data to a JSON file
with open('reddit_posts.json', 'w', encoding='utf-8') as f:
    json.dump(posts_data, f, ensure_ascii=False, indent=4)

print(f"Scraped data saved to reddit_posts.json")
