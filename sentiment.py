from nltk.sentiment import SentimentIntensityAnalyzer
import nltk

# Download once (will skip if already present)
# nltk.download('vader_lexicon', download_dir='./nltk_data')
# 👇 Add project-local nltk_data path
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
nltk.data.path.append(os.path.join(BASE_DIR, "../nltk_data"))

sia = SentimentIntensityAnalyzer()


def analyze_sentiment(tweet: str):
    score = sia.polarity_scores(tweet)
    compound = score["compound"]

    if compound >= 0.05:
        sentiment = "positive"
    elif compound <= -0.05:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    return sentiment, score


# # --- Test Data ---
test_tweets = [
    "I absolutely love this product! It's amazing 😍",          # positive
    "This is the worst experience I've ever had.",              # negative
    "The product is okay, nothing special.",                    # neutral
    "I'm happy with the service but the delivery was slow.",    # mixed (often neutral/positive)
    "I hate the UI but the performance is great."               # mixed sentiment
]


# # --- Run Test ---
if __name__ == "__main__":
    print("\nSentiment Analysis Results:\n")

    for tweet in test_tweets:
        sentiment, score = analyze_sentiment(tweet)
        print(f"Tweet: {tweet}")
        print(f"Sentiment: {sentiment}, Score: {score}")
        print("-" * 60)